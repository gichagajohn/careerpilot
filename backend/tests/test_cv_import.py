"""CV import — text extraction, deterministic parsing, and the API endpoint."""
from __future__ import annotations

import io
from pathlib import Path

import pytest

from app.services.cv_import import CvImportError, extract_text, parse_cv

SAMPLE_CV = """JOHN GICHAGA
Mathematics and Computer Studies Teacher
Nairobi, Kenya
johngichaga8@gmail.com | 0114094974
Nationality: Kenyan

PROFESSIONAL SUMMARY
Mathematics and Computer Studies teacher with First Class Honours B.Ed from
Gretsa University, currently teaching at Huruma Girls Senior School.

EDUCATION
Bachelor of Education (Arts), Gretsa University - First Class Honours, 2022 - 2025
Kenya Certificate of Secondary Education, Mang'u High School, 2018 - 2021

WORK EXPERIENCE
Mathematics and Computer Studies Teacher, Huruma Girls Senior School, 2026 - Present
Teaching Practice Intern, Gretsa University, 2024 - 2025

KEY SKILLS
Mathematics, Computer Studies, CBC Curriculum, Python

CERTIFICATIONS
TSC Registration Number TSC/987654, Teachers Service Commission
"""


@pytest.fixture()
def cv_txt(tmp_path) -> Path:
    path = tmp_path / "cv.txt"
    path.write_text(SAMPLE_CV, encoding="utf-8")
    return path


# ── Text extraction ─────────────────────────────────────────────


def test_extract_text_from_txt(cv_txt):
    assert "JOHN GICHAGA" in extract_text(cv_txt)


def test_extract_text_from_docx(tmp_path):
    docx = pytest.importorskip("docx")
    path = tmp_path / "cv.docx"
    document = docx.Document()
    for line in SAMPLE_CV.split("\n"):
        document.add_paragraph(line)
    document.save(str(path))
    assert "Gretsa University" in extract_text(path)


def test_extract_text_from_pdf(tmp_path):
    pytest.importorskip("pypdf")
    canvas_mod = pytest.importorskip("reportlab.pdfgen.canvas")
    path = tmp_path / "cv.pdf"
    c = canvas_mod.Canvas(str(path))
    y = 800
    for line in SAMPLE_CV.split("\n"):
        c.drawString(40, y, line[:95])
        y -= 14
    c.save()
    assert "johngichaga8@gmail.com" in extract_text(path)


def test_extract_text_rejects_unknown_format(tmp_path):
    path = tmp_path / "cv.xyz"
    path.write_text("nope", encoding="utf-8")
    with pytest.raises(CvImportError):
        extract_text(path)


# ── Deterministic parser ────────────────────────────────────────


def test_parser_extracts_contact_fields(cv_txt):
    result = parse_cv(extract_text(cv_txt))
    assert result.parser == "fallback"          # no LLM key configured in tests
    p = result.profile
    assert p.full_name == "John Gichaga"
    assert p.email == "johngichaga8@gmail.com"
    assert p.phone == "0114094974"
    assert p.nationality == "Kenyan"
    assert p.location == "Nairobi, Kenya"
    assert "Teacher" in (p.profession or "")


def test_parser_reports_which_fields_were_filled(cv_txt):
    result = parse_cv(extract_text(cv_txt))
    assert "full_name" in result.filled_fields
    assert "email" in result.filled_fields
    # filled_fields must only name fields that actually carry a value
    data = result.profile.model_dump()
    assert all(data[name] for name in result.filled_fields)


def test_parser_prefers_registration_line_with_a_number(cv_txt):
    result = parse_cv(extract_text(cv_txt))
    assert "TSC/987654" in (result.profile.professional_registration or "")


def test_parser_extracts_education_without_bleeding_fields(cv_txt):
    result = parse_cv(extract_text(cv_txt))
    degrees = {e.degree for e in result.education}
    assert "Bachelor of Education (Arts)" in degrees
    top = next(e for e in result.education if e.degree == "Bachelor of Education (Arts)")
    assert top.institution == "Gretsa University"      # no grade or dates mixed in
    assert top.classification == "First Class Honours"
    assert top.start_date == "2022" and top.end_date == "2025"


def test_parser_extracts_experience_and_current_role(cv_txt):
    result = parse_cv(extract_text(cv_txt))
    current = [e for e in result.experience if e.is_current]
    assert current, "the 'Present' role should be marked current"
    assert current[0].organization == "Huruma Girls Senior School"
    assert current[0].end_date is None


def test_parser_extracts_and_dedupes_skills():
    result = parse_cv("KEY SKILLS\nPython, python, Mathematics, Mathematics, CBC Curriculum")
    names = [s.name.lower() for s in result.skills]
    assert len(names) == len(set(names)), "skills must be de-duplicated"
    assert "python" in names


def test_parser_never_invents_data_for_a_sparse_cv():
    result = parse_cv("Some notes\nwith nothing useful in them at all")
    assert result.profile.email is None
    assert result.profile.phone is None
    assert result.education == []
    assert result.experience == []


def test_parser_handles_empty_text():
    result = parse_cv("   ")
    assert result.warnings
    assert result.filled_fields == []


# ── Endpoint ────────────────────────────────────────────────────


def _upload(client, headers, name="cv.txt", content=SAMPLE_CV):
    data = content if isinstance(content, bytes) else content.encode("utf-8")
    return client.post(
        "/api/v1/profile/import-cv",
        files={"file": (name, io.BytesIO(data), "text/plain")},
        headers=headers,
    )


def test_import_cv_returns_suggestions(client, auth_headers):
    r = _upload(client, auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["profile"]["full_name"] == "John Gichaga"
    assert body["education"] and body["experience"] and body["skills"]
    assert "full_name" in body["filled_fields"]


def test_import_cv_does_not_write_the_master_profile(client, auth_headers):
    """The whole point: suggestions are never auto-promoted."""
    _upload(client, auth_headers)
    profile = client.get("/api/v1/profile", headers=auth_headers).json()
    assert profile["profile_complete"] is False
    assert profile["full_name"] == "John Gichaga"   # from the account, not the CV
    assert profile["profession"] is None
    assert profile["education"] == []
    assert profile["skills"] == []


def test_import_cv_then_user_confirms_via_put(client, auth_headers):
    """The full intended flow: import -> review -> save."""
    suggested = _upload(client, auth_headers).json()

    r = client.put("/api/v1/profile", json=suggested["profile"], headers=auth_headers)
    assert r.status_code == 200, r.text
    for entry in suggested["education"]:
        assert client.post("/api/v1/profile/education", json=entry, headers=auth_headers).status_code == 201
    for skill in suggested["skills"]:
        client.post("/api/v1/profile/skills", json=skill, headers=auth_headers)

    profile = client.get("/api/v1/profile", headers=auth_headers).json()
    assert profile["profile_complete"] is True
    assert profile["phone"] == "0114094974"          # survived encryption round-trip
    assert len(profile["education"]) == len(suggested["education"])
    assert profile["skills"]


def test_import_cv_requires_authentication(client):
    r = client.post(
        "/api/v1/profile/import-cv",
        files={"file": ("cv.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert r.status_code == 401


def test_import_cv_rejects_unsupported_format(client, auth_headers):
    r = _upload(client, auth_headers, name="cv.exe", content="binary")
    assert r.status_code == 422
    assert "Unsupported" in r.json()["detail"]


def test_import_cv_rejects_empty_file(client, auth_headers):
    r = _upload(client, auth_headers, content="")
    assert r.status_code == 422


def test_import_cv_stores_document_for_the_owner_only(client, auth_headers):
    doc_id = _upload(client, auth_headers).json()["document_id"]
    assert doc_id is not None

    docs = client.get("/api/v1/documents", headers=auth_headers).json()
    assert any(d["id"] == doc_id and d["doc_type"] == "CV" for d in docs)

    other = client.post(
        "/api/v1/auth/register",
        json={"email": "cvother@example.com", "password": "StrongPass123", "full_name": "Other"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    assert client.get(f"/api/v1/documents/{doc_id}", headers=other_headers).status_code == 404
    assert client.get("/api/v1/documents", headers=other_headers).json() == []


def test_import_cv_extractions_are_unverified(client, auth_headers, db_session):
    """Audit trail must not claim the data is confirmed."""
    from app.models import DocumentExtraction

    doc_id = _upload(client, auth_headers).json()["document_id"]
    rows = db_session.query(DocumentExtraction).filter_by(document_id=doc_id).all()
    assert rows
    assert all(r.status == "UNVERIFIED" for r in rows)


# ── Section headings vary a lot between CVs ─────────────────────


@pytest.mark.parametrize("heading", [
    "KEY SKILLS", "SKILLS", "CORE COMPETENCIES", "AREAS OF EXPERTISE",
    "PROFESSIONAL SKILLS", "CORE SKILLS", "SKILLS & ABILITIES",
    "KEY SKILLS & COMPETENCIES", "TECHNICAL PROFICIENCIES", "Skills:", "Key Skills",
])
def test_skills_are_found_under_many_heading_styles(heading):
    result = parse_cv(f"{heading}\nMathematics, Python, CBC Curriculum")
    names = {s.name for s in result.skills}
    assert {"Mathematics", "Python", "CBC Curriculum"} <= names, f"failed for {heading!r}"


@pytest.mark.parametrize("heading", ["ACADEMIC QUALIFICATIONS", "EDUCATION", "Academic Background"])
def test_education_found_under_many_heading_styles(heading):
    result = parse_cv(f"{heading}\nBachelor of Education, Gretsa University, 2022 - 2025")
    assert result.education


@pytest.mark.parametrize("heading", ["WORK HISTORY", "EMPLOYMENT RECORD", "PROFESSIONAL BACKGROUND"])
def test_experience_found_under_many_heading_styles(heading):
    result = parse_cv(f"{heading}\nMaths Teacher, Huruma Girls, 2024 - Present")
    assert result.experience


def test_a_sentence_mentioning_skills_is_not_treated_as_a_heading():
    """Guard against the keyword matcher swallowing body text."""
    result = parse_cv(
        "PROFESSIONAL SUMMARY\n"
        "Skills gained during my teaching practice include classroom management.\n"
        "I have strong competencies in curriculum design and assessment.\n"
        "\n"
        "KEY SKILLS\n"
        "Mathematics, Python\n"
    )
    names = {s.name for s in result.skills}
    assert names == {"Mathematics", "Python"}
    assert "Skills gained during" in (result.profile.summary or "")
