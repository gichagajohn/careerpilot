"""Cover letter generator tests — role-specific, fact-checked, honest."""
from __future__ import annotations

from app.models import Education, Experience, Job, MasterProfile, Skill
from app.services.cover_letter import build_cover_letter, write_letter_docx, write_letter_pdf


def _profile(db) -> MasterProfile:
    from app.core.security import hash_password
    from app.models import User

    user = User(email="letter@example.com", password_hash=hash_password("StrongPass123"))
    db.add(user)
    db.flush()
    p = MasterProfile(user_id=user.id, full_name="John Gichaga", nationality="Kenyan",
                      location="Nairobi, Kenya", email="johngichaga8@gmail.com",
                      profession="Mathematics and Computer Studies Teacher",
                      professional_registration="Teacher Service Commission (TSC) registered teacher")
    db.add(p)
    db.flush()
    db.add(Education(profile_id=p.id, degree="Bachelor of Education (Arts)",
                     institution="Gretsa University", field="Mathematics and Computer Studies",
                     classification="First Class Honours"))
    db.add(Experience(profile_id=p.id, organization="Huruma Girls Senior School",
                      role="Mathematics and Computer Studies Teacher", start_date="2026-01",
                      is_current=True, subjects=["Mathematics", "Computer Studies"]))
    for name in ["Mathematics teaching", "Python", "JavaScript", "HTML", "CSS", "ICT integration"]:
        db.add(Skill(profile_id=p.id, name=name, approved=True))
    db.commit()
    db.refresh(p)
    return p


def _cs_job():
    return Job(title="Computer Science Teacher",
               organization_name="Bright Academy",
               description="Teach Computer Science and ICT. Python, JavaScript required. "
                           "Learner-centred pedagogy valued.",
               country="Kenya", curriculum="IGCSE")


def test_letter_is_role_specific_and_fact_checked(db_session):
    p = _profile(db_session)
    letter = build_cover_letter(p, _cs_job())
    assert letter.paragraphs  # not blocked
    assert letter.fact_check is not None
    assert letter.fact_check.removed_claims == 0
    text = letter.text.lower()
    assert "computer science teacher" in text or "computer science" in text
    assert "bright academy" in text           # names the employer
    assert "gretsa university" in text        # real qualification
    assert "tsc" in text or "service commission" in text
    assert "python" in text and "javascript" in text  # matched skills surfaced


def test_letter_differs_between_roles(db_session):
    p = _profile(db_session)
    math_job = Job(title="Mathematics Teacher", organization_name="Math School",
                   description="Teach Mathematics. Problem solving and assessment.",
                   country="Kenya")
    cs_letter = build_cover_letter(p, _cs_job())
    math_letter = build_cover_letter(p, math_job)
    assert cs_letter.text != math_letter.text


def test_letter_never_fabricates(db_session):
    p = _profile(db_session)
    letter = build_cover_letter(p, _cs_job())
    assert "international school experience" not in letter.text.lower()
    assert "10 years" not in letter.text.lower()  # years must match the profile


def test_letter_docx_pdf_written(tmp_path, db_session):
    p = _profile(db_session)
    letter = build_cover_letter(p, _cs_job())
    docx = write_letter_docx(letter, p, tmp_path / "letter.docx")
    pdf = write_letter_pdf(letter, p, tmp_path / "letter.pdf")
    assert docx.exists() and docx.stat().st_size > 500
    assert pdf.exists() and pdf.stat().st_size > 500
