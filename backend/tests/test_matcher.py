"""Matcher agent tests — scoring pass + notifications."""
from __future__ import annotations

from app.agents.matcher import run_matcher_pass
from app.models import Job, MasterProfile, Notification, Scholarship


def _profile(db_session) -> MasterProfile:
    from app.core.security import hash_password
    from app.models import Education, Skill, User

    user = User(email="matcher@example.com", password_hash=hash_password("StrongPass123"),
                full_name="Test")
    db_session.add(user)
    db_session.flush()
    p = MasterProfile(user_id=user.id, full_name="John Gichaga", nationality="Kenyan",
                      location="Nairobi, Kenya",
                      professional_registration="Teacher Service Commission (TSC) registered teacher")
    db_session.add(p)
    db_session.flush()
    db_session.add(Education(profile_id=p.id, degree="Bachelor of Education (Arts)",
                             field="Mathematics and Computer Studies",
                             classification="First Class Honours"))
    for name in ["Python", "JavaScript", "Microsoft Excel"]:
        db_session.add(Skill(profile_id=p.id, name=name, approved=True))
    db_session.commit()
    db_session.refresh(p)
    return p


def test_matcher_scores_and_notifies(db_session):
    _profile(db_session)
    db_session.add(Job(
        title="Mathematics Teacher", organization_name="Bright Academy",
        location="Nairobi, Kenya", country="Kenya",
        description="Teach Mathematics and Computer Studies. Bachelor's degree required. "
                    "TSC registration. Full-time at a school in Nairobi.",
        status="DISCOVERED", verification_status="VERIFIED",
    ))
    db_session.add(Scholarship(
        name="Erasmus Mundus Joint Master", university="EU consortium", country="Europe",
        degree_level="Master's", funding_level="FULLY FUNDED",
        required_classification="First Class Honours", required_field="Mathematics Education",
        open_to_kenyans=True,
    ))
    db_session.commit()

    stats = run_matcher_pass(db_session, force=True, user_id=1)

    assert stats["jobs_scored"] == 1
    assert stats["scholarships_scored"] == 1

    job = db_session.query(Job).one()
    assert job.match_score is not None and job.match_score >= 70
    assert job.eligibility == "ELIGIBLE"
    assert job.priority_score is not None
    assert job.match_details["strengths"]  # "why you match" populated

    sch = db_session.query(Scholarship).one()
    assert sch.match_score is not None and sch.match_score >= 70

    # high-match notifications created (in-app)
    types = {n.type for n in db_session.query(Notification).all()}
    assert "HIGH_MATCH" in types


def test_matcher_idempotent_notifications(db_session):
    _profile(db_session)
    db_session.add(Job(
        title="Mathematics Teacher", organization_name="Bright Academy",
        location="Nairobi, Kenya", country="Kenya",
        description="Teach Mathematics. Bachelor's degree required.",
        status="DISCOVERED", verification_status="VERIFIED",
    ))
    db_session.commit()

    run_matcher_pass(db_session, force=True, user_id=1)
    run_matcher_pass(db_session, force=True, user_id=1)

    assert db_session.query(Notification).filter_by(type="HIGH_MATCH").count() == 1
