"""Eligibility Analyst tests — deterministic rubric (spec §6)."""
from __future__ import annotations

from app.models import Education, Experience, Job, MasterProfile, Scholarship, Skill
from app.services.scoring import (
    compute_job_eligibility,
    compute_priority,
    compute_relevance,
    compute_scholarship_eligibility,
    deadline_component,
    profile_years_experience,
)


def _profile(db) -> MasterProfile:
    from app.core.security import hash_password
    from app.models import User

    user = User(email=f"prof{id(db)}@example.com",
                password_hash=hash_password("StrongPass123"), full_name="Test")
    db.add(user)
    db.flush()
    profile = MasterProfile(
        user_id=user.id,
        full_name="John Gichaga", nationality="Kenyan", location="Nairobi, Kenya",
        professional_registration="Teacher Service Commission (TSC) registered teacher",
    )
    db.add(profile)
    db.flush()
    db.add(Education(profile_id=profile.id, degree="Bachelor of Education (Arts)",
                     field="Mathematics and Computer Studies",
                     classification="First Class Honours"))
    db.add(Experience(profile_id=profile.id, organization="Huruma Girls Senior School",
                      role="Mathematics and Computer Studies Teacher",
                      start_date="2026-01", is_current=True,
                      subjects=["Mathematics", "Computer Studies"]))
    db.add(Experience(profile_id=profile.id, organization="Happyland Greenspan Spring",
                      start_date="2025-09", end_date="2025-12",
                      subjects=["Mathematics", "ICT"]))
    for name in ["Python", "HTML", "CSS", "JavaScript", "Microsoft Excel", "Data analysis"]:
        db.add(Skill(profile_id=profile.id, name=name, approved=True))
    db.commit()
    db.refresh(profile)
    return profile


def _job(title="Mathematics Teacher", description="Teach Mathematics.",
         country="Kenya", verification_status="VERIFIED", **kw):
    return Job(
        title=title, description=description, country=country,
        location=kw.pop("location", "Nairobi, Kenya"),
        status=kw.pop("status", "DISCOVERED"),
        verification_status=verification_status, **kw,
    )


def test_years_experience_computed(db_session):
    p = _profile(db_session)
    years = profile_years_experience(p)
    assert 0.7 <= years <= 3.0  # ~1 year of experience on record


def test_matching_math_job_is_eligible(db_session):
    p = _profile(db_session)
    job = _job(description="Teach Mathematics and Computer Studies at a secondary school. "
                           "Bachelor's degree required. TSC registration required.")
    result = compute_job_eligibility(p, job)
    assert result.label == "ELIGIBLE"
    assert result.score >= 70
    assert result.components["subject_match"] == 20
    assert result.components["registration"] == 10
    assert result.components["location"] == 10
    assert any("TSC" in s for s in result.strengths)


def test_missing_subject_gap_surface(db_session):
    p = _profile(db_session)
    job = _job(title="Physics and Mathematics Teacher",
               description="Teach Physics and Mathematics.")
    result = compute_job_eligibility(p, job)
    assert result.components["subject_match"] == 10  # math covered, physics not
    assert any("physics" in g.lower() for g in result.gaps)


def test_international_not_eligible_without_relocation(db_session):
    p = _profile(db_session)
    job = _job(description="Teach Mathematics.", country="United Arab Emirates",
               location="Dubai", is_international=True)
    result = compute_job_eligibility(p, job)
    assert result.components["location"] == 0
    assert any("International" in g for g in result.gaps)


def test_expired_risk_surface(db_session):
    p = _profile(db_session)
    job = _job(description="Teach Mathematics.", deadline="2020-01-01",
               verification_status="EXPIRED")
    result = compute_job_eligibility(p, job)
    assert any("passed" in r.lower() for r in result.risks)


def test_scholarship_eligibility(db_session):
    p = _profile(db_session)
    sch = Scholarship(
        name="DAAD Mathematics Education Scholarship",
        university="University of Bonn", country="Germany", degree_level="Master's",
        required_classification="First Class Honours",
        required_field="Mathematics Education",
        open_to_kenyans=True, funding_level="FULLY FUNDED",
    )
    result = compute_scholarship_eligibility(p, sch)
    assert result.score >= 70
    assert result.label == "ELIGIBLE"
    assert result.components["classification"] == 15
    assert result.components["kenya_africa"] == 10


def test_scholarship_field_gap(db_session):
    p = _profile(db_session)
    sch = Scholarship(
        name="Marine Biology Scholarship", university="U", country="Norway",
        required_field="Marine Biology", open_to_africans=True,
    )
    result = compute_scholarship_eligibility(p, sch)
    assert result.components["field"] < 20
    assert any("biology" in g.lower() for g in result.gaps)


def test_relevance_scores_higher_for_related_text(db_session):
    p = _profile(db_session)
    assert compute_relevance(p, "Mathematics Computer Studies teacher Python") > compute_relevance(
        p, "Sales marketing advertising copywriting")


def test_priority_with_custom_weights():
    # Eligibility 100, everything else 0 → priority = 30 with default weights
    assert compute_priority(100, 0, 0, 0, 0, 0) == 30.0
    assert compute_priority(100, 100, 1, 1, 1, 1) == 100.0


def test_deadline_component():
    assert deadline_component("2020-01-01") == 0.0  # expired
    assert deadline_component(None) == 0.5
