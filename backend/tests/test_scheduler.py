"""Scheduler tests — cadence mapping and API trigger."""
from __future__ import annotations

from app.agents.job_scout import _is_due, load_queries
from app.models import SearchSource
from app.services.scheduler import cron_hour_expr


def test_cron_hour_expr():
    assert cron_hour_expr([0, 8, 16]) == "0,8,16"
    assert cron_hour_expr([6]) == "6"


def test_query_catalog_has_core_terms():
    queries = load_queries()
    assert len(queries) >= 25  # the 25 search categories from spec §3
    core = [q for q in queries if q.get("core")]
    assert core  # quota-safe subset for Adzuna


def test_is_due_logic(db_session):
    src = SearchSource(name="x", kind="API", category="jobs", cadence="3x", enabled=True)
    assert _is_due(src) is True  # never run before

    src.last_run_at = "2026-08-18T10:00:00+03:00"
    assert _is_due(src) is False  # just ran

    src.cadence = "daily"
    assert _is_due(src) is False  # daily = 20h window

    src.last_run_at = "2026-08-01T10:00:00+03:00"
    assert _is_due(src) is True
