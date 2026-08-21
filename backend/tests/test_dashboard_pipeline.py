"""Regression tests: the dashboard must actually be able to fill up.

Covers the three defects that left it permanently empty or wrong:
  1. search_sources was only ever created by scripts/seed.py, so an unseeded
     deployment ran discovery against zero sources — a silent no-op.
  2. Agents picked "the first active profile in the table" rather than the
     relevant user's, which after the profile fix could be an empty placeholder.
  3. /dashboard/summary counted every user's applications.
"""
from __future__ import annotations

from sqlalchemy import select

from app.models import Application, Job, MasterProfile, SearchSource, User
from app.services.profile_lookup import active_profile_for, profile_is_populated
from app.services.sources.defaults import ALL_DEFAULT_SOURCES, ensure_default_sources


# ── 1. Discovery sources are provisioned automatically ──────────


def test_default_sources_are_provisioned_on_startup(client, db_session):
    """The app lifespan runs bootstrap_sources, so a fresh DB is productive."""
    count = db_session.scalar(select(SearchSource).with_only_columns(SearchSource.id).limit(1))
    assert count is not None, "startup should have created discovery sources"

    names = {s.name for s in db_session.scalars(select(SearchSource)).all()}
    assert {"remotive", "remoteok", "arbeitnow", "rss", "adzuna", "websearch"} <= names
    assert any(n.startswith("scholarship_") for n in names)


def test_jobscout_has_sources_to_run(client, auth_headers):
    """Before the fix this returned sources_run=0 with no error."""
    sources = client.get("/api/v1/agents/sources", headers=auth_headers).json()
    assert len(sources) >= len(ALL_DEFAULT_SOURCES)
    job_sources = [s for s in sources if s["category"] == "jobs"]
    assert len(job_sources) >= 6


def test_ensure_default_sources_is_idempotent(db_session):
    first = ensure_default_sources(db_session)
    assert first == len(ALL_DEFAULT_SOURCES)

    second = ensure_default_sources(db_session)
    assert second == 0, "re-running must not duplicate sources"

    total = len(db_session.scalars(select(SearchSource)).all())
    assert total == len(ALL_DEFAULT_SOURCES)


def test_ensure_default_sources_preserves_user_edits(db_session):
    """A source the user disabled must stay disabled."""
    ensure_default_sources(db_session)
    src = db_session.scalar(select(SearchSource).where(SearchSource.name == "remotive"))
    src.enabled = False
    db_session.commit()

    ensure_default_sources(db_session)
    db_session.refresh(src)
    assert src.enabled is False


# ── 2. Agents resolve the right user's profile ──────────────────


def _make_user(db, email: str, *, populated: bool) -> User:
    user = User(email=email, password_hash="x", full_name="Test User")
    db.add(user)
    db.flush()
    profile = MasterProfile(
        user_id=user.id,
        full_name="Test User",
        email=email,
        profession="Mathematics Teacher" if populated else None,
        is_active=True,
    )
    db.add(profile)
    db.commit()
    return user


def test_empty_placeholder_profile_is_not_usable(db_session):
    user = _make_user(db_session, "empty@example.com", populated=False)
    profile = db_session.scalar(select(MasterProfile).where(MasterProfile.user_id == user.id))
    assert profile_is_populated(profile) is False
    assert active_profile_for(db_session, user.id) is None


def test_agent_never_borrows_another_users_profile(db_session):
    """The core leak: user B's empty profile must not resolve to user A's data."""
    first = _make_user(db_session, "first@example.com", populated=True)
    second = _make_user(db_session, "second@example.com", populated=False)

    assert active_profile_for(db_session, first.id).user_id == first.id
    # Second user has nothing usable — must be None, NOT the first user's row.
    assert active_profile_for(db_session, second.id) is None


def test_scheduler_fallback_skips_empty_placeholders(db_session):
    """With no request context, pick the first *populated* profile."""
    _make_user(db_session, "placeholder@example.com", populated=False)  # lower id
    real = _make_user(db_session, "real@example.com", populated=True)

    resolved = active_profile_for(db_session, None)
    assert resolved is not None
    assert resolved.user_id == real.id


def test_matcher_reports_a_clear_error_without_a_profile(db_session):
    from app.agents.matcher import run_matcher_pass

    user = _make_user(db_session, "noprofile@example.com", populated=False)
    db_session.add(Job(title="Mathematics Teacher", organization_name="A School",
                       status="DISCOVERED", verification_status="VERIFIED"))
    db_session.commit()

    stats = run_matcher_pass(db_session, force=True, user_id=user.id)
    assert stats["jobs_scored"] == 0
    assert stats["errors"]
    assert "master profile" in stats["errors"][0].lower()


def test_profile_with_only_education_is_usable(db_session):
    """Scoring needs substance, not specifically a 'profession' string."""
    from app.models import Education

    user = _make_user(db_session, "edu@example.com", populated=False)
    profile = db_session.scalar(select(MasterProfile).where(MasterProfile.user_id == user.id))
    db_session.add(Education(profile_id=profile.id, degree="B.Ed", institution="Gretsa"))
    db_session.commit()
    db_session.refresh(profile)

    assert profile_is_populated(profile) is True
    assert active_profile_for(db_session, user.id).id == profile.id


# ── 3. Dashboard counts only your own applications ──────────────


def test_dashboard_applications_are_per_user(client, auth_headers, db_session):
    job = Job(title="Mathematics Teacher", organization_name="A School",
              status="DISCOVERED", verification_status="VERIFIED")
    db_session.add(job)
    db_session.flush()

    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    other = _make_user(db_session, "otherapps@example.com", populated=True)

    # Three applications belonging to somebody else, one of them an offer.
    for status_value in ("APPLIED", "INTERVIEW", "OFFER"):
        db_session.add(Application(user_id=other.id, job_id=job.id, status=status_value))
    db_session.commit()

    summary = client.get("/api/v1/dashboard/summary", headers=auth_headers).json()
    assert summary["applications_total"] == 0
    assert summary["applications_interviews"] == 0
    assert summary["applications_offers"] == 0

    # My own application shows up, and only mine.
    db_session.add(Application(user_id=me["id"], job_id=job.id, status="INTERVIEW"))
    db_session.commit()

    summary = client.get("/api/v1/dashboard/summary", headers=auth_headers).json()
    assert summary["applications_total"] == 1
    assert summary["applications_interviews"] == 1
    assert summary["applications_offers"] == 0


def test_dashboard_counts_opportunities(client, auth_headers, db_session):
    """Opportunities remain a shared pool — that part is by design."""
    db_session.add(Job(title="Mathematics Teacher", organization_name="A School",
                       status="DISCOVERED", verification_status="VERIFIED", match_score=91.0))
    db_session.commit()

    summary = client.get("/api/v1/dashboard/summary", headers=auth_headers).json()
    assert summary["total_opportunities"] == 1
    assert summary["high_match_opportunities"] == 1


# ── 4. Sources can be run one at a time (proxy request-timeout workaround) ──


def test_jobscout_accepts_a_single_source(client, auth_headers):
    """Long sweeps exceed hosting proxy request limits; per-source keeps them short."""
    r = client.post(
        "/api/v1/agents/jobscout/run?force=true&sources=remoteok", headers=auth_headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["sources_run"] <= 1


def test_jobscout_accepts_several_named_sources(client, auth_headers):
    r = client.post(
        "/api/v1/agents/jobscout/run?force=true&sources=remoteok,arbeitnow",
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["sources_run"] <= 2


def test_scholarshipscout_accepts_a_single_source(client, auth_headers):
    r = client.post(
        "/api/v1/agents/scholarshipscout/run?force=true&sources=scholarship_daad",
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["sources_run"] <= 1


def test_omitting_sources_still_runs_everything(client, auth_headers):
    """Backwards compatible: no `sources` param means the full sweep."""
    from app.api.routers.agents import _split_sources

    assert _split_sources(None) is None
    assert _split_sources("") is None
    assert _split_sources("  ") is None
    assert _split_sources("a, b ,,c") == ["a", "b", "c"]
