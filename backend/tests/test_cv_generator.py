"""CV generator tests — tailoring, docx/pdf output, honest by construction."""
from __future__ import annotations

import json

from app.models import Education, Experience, Job, MasterProfile, Skill
from app.services.cv_generator import build_cv, detect_role_type, write_docx, write_pdf


def _profile(db) -> MasterProfile:
    from app.core.security import hash_password
    from app.models import User

    user = User(email="cv@example.com", password_hash=hash_password("StrongPass123"))
    db.add(user)
    db.flush()
    p = MasterProfile(user_id=user.id, full_name="John Gichaga", nationality="Kenyan",
                      location="Nairobi, Kenya", phone_encrypted=None,
                      email="johngichaga8@gmail.com", profession="Mathematics and Computer Studies Teacher",
                      professional_registration="Teacher Service Commission (TSC) registered teacher")
    db.add(p)
    db.flush()
    db.add(Education(profile_id=p.id, degree="Bachelor of Education (Arts)",
                     institution="Gretsa University", field="Mathematics and Computer Studies",
                     classification="First Class Honours", start_date="2022", end_date="2025"))
    db.add(Experience(profile_id=p.id, organization="Huruma Girls Senior School",
                      role="Mathematics and Computer Studies Teacher", start_date="2026-01",
                      is_current=True, subjects=["Mathematics", "Computer Studies"]))
    for name in ["Mathematics teaching", "Python", "HTML", "CSS", "JavaScript",
                 "Microsoft Excel", "ICT integration", "CBC/CBE pedagogy"]:
        db.add(Skill(profile_id=p.id, name=name, approved=True))
    db.commit()
    db.refresh(p)
    return p


def _cs_job():
    return Job(title="Computer Science Teacher",
               description="Teach Computer Science and ICT at an international school. "
                           "JavaScript, Python, HTML, CSS required.",
               country="Kenya", curriculum="IGCSE")


def test_role_detection():
    assert detect_role_type(_cs_job()) == "computer_science"
    math_job = Job(title="Mathematics Teacher", description="Teach mathematics and assessment.")
    assert detect_role_type(math_job) == "math"


def test_cv_built_from_profile_only(db_session):
    p = _profile(db_session)
    cv = build_cv(p, _cs_job())
    assert cv.sections  # not blocked
    assert cv.fact_check is not None
    assert cv.fact_check.removed_claims == 0  # nothing fabricated to remove

    # relevant skills surface first for CS roles
    skills_line = cv.sections["SKILLS"][0].lower()
    assert skills_line.index("python") < skills_line.index("microsoft excel")

    # no invented content: international/IGCSE claims absent from profile → not claimed
    all_text = " ".join(cv.lines()).lower()
    assert "international school experience" not in all_text


def test_cv_docx_and_pdf_written(tmp_path, db_session):
    p = _profile(db_session)
    cv = build_cv(p, _cs_job())
    docx = write_docx(cv, tmp_path / "cv.docx")
    pdf = write_pdf(cv, tmp_path / "cv.pdf")
    assert docx.exists() and docx.stat().st_size > 500
    assert pdf.exists() and pdf.stat().st_size > 500


def test_cv_has_no_forbidden_sections(db_session):
    p = _profile(db_session)
    cv = build_cv(p, _cs_job())
    headings = [h for h in cv.sections if cv.sections[h]]
    assert not any("reference" in h.lower() for h in headings)
    assert not any("salary" in h.lower() for h in headings)
