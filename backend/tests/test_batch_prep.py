"""Batch application preparation and the review queue.

The rule these tests protect: preparation is automated, submission is not.
"""
from __future__ import annotations

from sqlalchemy import select

from app.models import Application, Education, Job, MasterProfile, Skill, User


def _profile(db, user_id: int) -> MasterProfile:
    profile = db.scalar(select(MasterProfile).where(MasterProfile.user_id == user_id))
    profile.full_name = "John Gichaga"
    profile.profession = "Mathematics and Computer Studies Teacher"
    profile.location = "Nairobi, Kenya"
    profile.professional_registration = "TSC registered teacher"
    db.flush()
    db.add(Education(profile_id=profile.id, degree="Bachelor of Education (Arts)",
                     institution="Gretsa University", field="Mathematics and Computer Studies",
                     classification="First Class Honours", start_date="2022", end_date="2025"))
    for name in ("Mathematics", "Computer Studies", "Lesson Planning"):
        db.add(Skill(profile_id=profile.id, name=name, approved=True))
    db.commit()
    return profile


def _job(db, title="Mathematics Teacher", score=90.0, verification="VERIFIED", **kw) -> Job:
    job = Job(
        title=title, organization_name="Bright Academy", location="Nairobi, Kenya",
        country="Kenya", description="Teach Mathematics and Computer Studies at a Nairobi school.",
        status="DISCOVERED", verification_status=verification, is_canonical=True,
        match_score=score, priority_score=score, application_url="https://example.com/apply",
        # Real jobs always arrive through JobIn, whose list fields default to [].
        # Mirror that here so the fixture matches production data.
        requirements=[], preferred_requirements=[],
        **kw,
    )
    db.add(job)
    db.commit()
    return job


def _setup(client, db_session, auth_headers, n_jobs=3):
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    _profile(db_session, me["id"])
    for i in range(n_jobs):
        _job(db_session, title=f"Mathematics Teacher {i}", score=90.0 - i)
    return me


# ── Preparation ─────────────────────────────────────────────────


def test_prepare_batch_creates_applications_with_documents(client, auth_headers, db_session):
    _setup(client, db_session, auth_headers, n_jobs=3)

    r = client.post("/api/v1/applications/prepare-batch?limit=2", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["candidates_found"] == 2
    assert body["prepared"] == 2
    for item in body["items"]:
        assert item["application_id"]
        assert item["cv_version_id"], item["problems"]
        assert item["cover_letter_id"], item["problems"]
        assert item["status"] == "READY FOR REVIEW"


def test_prepare_batch_never_submits_anything(client, auth_headers, db_session):
    """The whole point: prepared, not sent."""
    _setup(client, db_session, auth_headers, n_jobs=2)
    client.post("/api/v1/applications/prepare-batch?limit=2", headers=auth_headers)

    rows = db_session.scalars(select(Application)).all()
    assert rows
    assert all(r.status == "READY FOR REVIEW" for r in rows)
    assert all(r.date_applied is None for r in rows), "nothing may be marked as applied"


def test_prepare_batch_respects_the_limit(client, auth_headers, db_session):
    _setup(client, db_session, auth_headers, n_jobs=6)
    body = client.post("/api/v1/applications/prepare-batch?limit=3", headers=auth_headers).json()
    assert body["prepared"] == 3


def test_prepare_batch_skips_expired_and_suspicious(client, auth_headers, db_session):
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    _profile(db_session, me["id"])
    _job(db_session, title="Good role", score=90.0, verification="VERIFIED")
    _job(db_session, title="Old role", score=95.0, verification="EXPIRED")
    _job(db_session, title="Dodgy role", score=99.0, verification="SUSPICIOUS")

    body = client.post("/api/v1/applications/prepare-batch?limit=5", headers=auth_headers).json()
    titles = {i["title"] for i in body["items"]}
    assert titles == {"Good role"}


def test_prepare_batch_respects_min_score(client, auth_headers, db_session):
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    _profile(db_session, me["id"])
    _job(db_session, title="Strong", score=92.0)
    _job(db_session, title="Weak", score=40.0)

    body = client.post("/api/v1/applications/prepare-batch?limit=5&min_score=80",
                       headers=auth_headers).json()
    assert {i["title"] for i in body["items"]} == {"Strong"}


def test_prepare_batch_does_not_duplicate_existing_applications(client, auth_headers, db_session):
    _setup(client, db_session, auth_headers, n_jobs=2)
    first = client.post("/api/v1/applications/prepare-batch?limit=5", headers=auth_headers).json()
    assert first["prepared"] == 2

    second = client.post("/api/v1/applications/prepare-batch?limit=5", headers=auth_headers).json()
    assert second["candidates_found"] == 0
    assert second["prepared"] == 0
    assert len(db_session.scalars(select(Application)).all()) == 2


def test_prepare_batch_without_a_profile_fails_gracefully(client, auth_headers, db_session):
    """No master profile: report the problem, do not crash or half-create."""
    _job(db_session, title="Mathematics Teacher", score=90.0)
    r = client.post("/api/v1/applications/prepare-batch?limit=1", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["prepared"] == 0
    assert body["incomplete"] == 1
    assert body["items"][0]["problems"]


def test_prepare_batch_requires_authentication(client):
    assert client.post("/api/v1/applications/prepare-batch").status_code == 401


# ── Review queue ────────────────────────────────────────────────


def test_review_queue_returns_everything_needed_to_submit(client, auth_headers, db_session):
    _setup(client, db_session, auth_headers, n_jobs=1)
    client.post("/api/v1/applications/prepare-batch?limit=1", headers=auth_headers)

    items = client.get("/api/v1/applications/review-queue", headers=auth_headers).json()
    assert len(items) == 1
    it = items[0]
    assert it["status"] == "READY FOR REVIEW"
    assert it["apply_url"] == "https://example.com/apply"
    assert it["cv_pdf"] and it["cv_docx"]
    assert it["letter_pdf"] and it["letter_docx"]
    assert it["match_score"] is not None


def test_marking_applied_removes_it_from_the_queue(client, auth_headers, db_session):
    _setup(client, db_session, auth_headers, n_jobs=1)
    client.post("/api/v1/applications/prepare-batch?limit=1", headers=auth_headers)
    item = client.get("/api/v1/applications/review-queue", headers=auth_headers).json()[0]

    r = client.patch(f"/api/v1/applications/{item['application_id']}",
                     json={"status": "APPLIED"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["date_applied"], "PATCH should stamp the applied date"

    assert client.get("/api/v1/applications/review-queue", headers=auth_headers).json() == []


def test_review_queue_is_private_to_its_owner(client, auth_headers, db_session):
    _setup(client, db_session, auth_headers, n_jobs=1)
    client.post("/api/v1/applications/prepare-batch?limit=1", headers=auth_headers)

    other = client.post("/api/v1/auth/register",
                        json={"email": "rq@example.com", "password": "StrongPass123",
                              "full_name": "Other"})
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    assert client.get("/api/v1/applications/review-queue", headers=other_headers).json() == []


def test_another_user_cannot_mark_my_application_applied(client, auth_headers, db_session):
    _setup(client, db_session, auth_headers, n_jobs=1)
    client.post("/api/v1/applications/prepare-batch?limit=1", headers=auth_headers)
    item = client.get("/api/v1/applications/review-queue", headers=auth_headers).json()[0]

    other = client.post("/api/v1/auth/register",
                        json={"email": "rq2@example.com", "password": "StrongPass123",
                              "full_name": "Other"})
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    r = client.patch(f"/api/v1/applications/{item['application_id']}",
                     json={"status": "APPLIED"}, headers=other_headers)
    assert r.status_code == 404


def test_batch_is_capped_to_protect_the_server(client, auth_headers, db_session):
    from app.services.batch_prep import MAX_BATCH

    _setup(client, db_session, auth_headers, n_jobs=2)
    body = client.post(f"/api/v1/applications/prepare-batch?limit={MAX_BATCH + 50}",
                       headers=auth_headers).json()
    assert body["requested"] == MAX_BATCH
