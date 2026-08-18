"""FactCheck gate tests — the anti-fabrication core (spec §22)."""
from __future__ import annotations

from app.models import Education, Experience, MasterProfile, Skill
from app.services.fact_check import (
    build_fact_store,
    fact_check_document,
    verify_line,
)


def _profile(db) -> MasterProfile:
    from app.core.security import hash_password
    from app.models import User

    user = User(email="fc@example.com", password_hash=hash_password("StrongPass123"))
    db.add(user)
    db.flush()
    p = MasterProfile(user_id=user.id, full_name="John Gichaga", nationality="Kenyan",
                      location="Nairobi, Kenya",
                      professional_registration="Teacher Service Commission (TSC) registered teacher")
    db.add(p)
    db.flush()
    db.add(Education(profile_id=p.id, degree="Bachelor of Education (Arts)",
                     institution="Gretsa University", field="Mathematics and Computer Studies",
                     classification="First Class Honours"))
    db.add(Experience(profile_id=p.id, organization="Huruma Girls Senior School",
                      role="Mathematics Teacher", start_date="2026-01", is_current=True,
                      subjects=["Mathematics", "Computer Studies"]))
    db.add(Skill(profile_id=p.id, name="Python", approved=True))
    db.add(Skill(profile_id=p.id, name="JavaScript", approved=True))
    db.commit()
    db.refresh(p)
    return p


def test_verified_lines_kept(db_session):
    p = _profile(db_session)
    lines = [
        "John Gichaga",
        "Bachelor of Education (Arts) — Gretsa University — First Class Honours",
        "Mathematics Teacher — Huruma Girls Senior School",
        "Subjects: Mathematics, Computer Studies",
        "Python, JavaScript",
    ]
    report, kept = fact_check_document(lines, p)
    assert report.total_claims == 5
    assert report.verified_claims == 5
    assert len(kept) == 5


def test_invented_facts_removed(db_session):
    p = _profile(db_session)
    lines = [
        "Mathematics Teacher — Harvard International School",   # org NOT in profile
        "Master of Science in AI from Oxford University",       # degree NOT in profile
        "Skills: Rust, Kubernetes",                             # skills NOT in profile
        "Mathematics Teacher — Huruma Girls Senior School",     # legit
    ]
    report, kept = fact_check_document(lines, p)
    assert report.removed_claims == 3
    assert len(kept) == 1
    assert "Huruma" in kept[0]


def test_prohibited_patterns_void_document(db_session):
    p = _profile(db_session)
    lines = [
        "Mathematics Teacher — Huruma Girls Senior School",
        "With 3 years of international school teaching experience in IGCSE",  # fabricated
    ]
    report, kept = fact_check_document(lines, p)
    assert report.prohibited_findings
    assert kept == []  # hard rule: whole document voided


def test_verify_line_missing_term_fails(db_session):
    p = _profile(db_session)
    store = build_fact_store(p)
    assert verify_line("Taught at Oxford University", store).verified is False
    assert verify_line("Mathematics Teacher", store).verified is True
