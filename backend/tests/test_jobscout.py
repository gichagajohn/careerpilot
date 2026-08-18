"""JobScout end-to-end tests with a mocked source adapter."""
from __future__ import annotations

from app.agents.job_scout import run_job_scout
from app.models import Job, JobSource, SearchRun, SearchSource
from app.services.sources.base import RawListing


class _FakeAdapter:
    name = "testfeed"
    kind = "API"

    def fetch(self, db, query, limit=20):  # noqa: ARG002
        return [
            RawListing(
                title="Mathematics Teacher",
                url="https://source-a.example/math-teacher",
                raw_text="Mathematics Teacher at Bright Academy Nairobi. Full-time. "
                         "Requirements: B.Ed Mathematics, TSC registration.",
                source_name="testfeed",
                source_type="API",
            ),
            RawListing(
                title="Mathematics Teacher",
                url="https://source-b.example/math-teacher-kenya",
                raw_text="Mathematics Teacher at Bright Academy Nairobi. Full-time.",
                source_name="testfeed",
                source_type="API",
            ),
        ]


def _add_source(db, name="testfeed", cadence="3x", last_run_at=None):
    src = SearchSource(
        name=name, kind="API", url="https://example.com/feed", category="jobs",
        cadence=cadence, enabled=True, last_run_at=last_run_at,
    )
    db.add(src)
    db.commit()
    db.refresh(src)
    return src


def test_jobscout_full_pipeline(monkeypatch, db_session):
    from app.agents import job_scout as module

    _add_source(db_session)
    monkeypatch.setitem(module.ADAPTERS, "testfeed", _FakeAdapter)

    stats = run_job_scout(db_session, queries=["Mathematics Teacher"], force=True)

    assert stats["sources_run"] == 1
    assert stats["queries_run"] == 1
    assert stats["listings"] == 2
    assert stats["new_jobs"] == 1          # both listings collapse into one job
    assert stats["duplicates"] == 1        # second listing merged as a source
    assert stats["errors"] == []

    jobs = db_session.query(Job).all()
    assert len(jobs) == 1
    assert jobs[0].title == "Mathematics Teacher"
    assert jobs[0].verification_status == "UNVERIFIED"
    assert jobs[0].status == "DISCOVERED"

    sources = db_session.query(JobSource).filter(JobSource.job_id == jobs[0].id).all()
    assert len(sources) == 2               # one job, two source URLs (spec §24)

    runs = db_session.query(SearchRun).all()
    assert len(runs) == 1
    assert runs[0].results_found == 2


def test_jobscout_cadence_skips_recent_run(monkeypatch, db_session):
    from datetime import datetime

    from app.agents import job_scout as module

    _add_source(db_session, last_run_at=datetime.now().astimezone().isoformat(timespec="seconds"))
    monkeypatch.setitem(module.ADAPTERS, "testfeed", _FakeAdapter)

    stats = run_job_scout(db_session, queries=["Mathematics Teacher"], force=False)
    assert stats["sources_run"] == 0       # not due yet (cadence 3x ≈ every 7h)


def test_jobscout_force_overrides_cadence(monkeypatch, db_session):
    from app.agents import job_scout as module

    _add_source(db_session, last_run_at="2026-08-17T12:00:00+03:00")
    monkeypatch.setitem(module.ADAPTERS, "testfeed", _FakeAdapter)

    stats = run_job_scout(db_session, queries=["Mathematics Teacher"], force=True)
    assert stats["sources_run"] == 1
    assert stats["new_jobs"] == 1


def test_jobscout_repeat_run_no_duplicates(monkeypatch, db_session):
    """A second forced run of identical listings adds no new rows and no new sources."""
    from app.agents import job_scout as module

    _add_source(db_session)
    monkeypatch.setitem(module.ADAPTERS, "testfeed", _FakeAdapter)

    first = run_job_scout(db_session, queries=["Mathematics Teacher"], force=True)
    second = run_job_scout(db_session, queries=["Mathematics Teacher"], force=True)

    assert first["new_jobs"] == 1
    assert second["new_jobs"] == 0
    assert second["duplicates"] == 0       # identical URLs already attached
    assert db_session.query(Job).count() == 1


def test_jobscout_disabled_source_skipped(monkeypatch, db_session):
    from app.agents import job_scout as module

    src = _add_source(db_session)
    src.enabled = False
    db_session.commit()
    monkeypatch.setitem(module.ADAPTERS, "testfeed", _FakeAdapter)

    stats = run_job_scout(db_session, queries=["Mathematics Teacher"], force=True)
    assert stats["sources_run"] == 0
