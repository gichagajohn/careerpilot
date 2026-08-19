"""Scheduler tests — cadence mapping and API trigger."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

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


def _iso(dt: datetime) -> str:
    """Render a datetime as the same ISO string format the model uses."""
    return dt.isoformat(timespec="seconds")


def test_is_due_logic(db_session):
    """Verify _is_due correctly interprets the cadence map.

    Uses RELATIVE timestamps (computed from datetime.now()) so the test
    remains correct forever, not just on the day it was written.
    """
    now = datetime.now().astimezone()

    # ── Case 1: never run → must be due immediately ─────────────────────
    src = SearchSource(name="x", kind="API", category="jobs", cadence="3x", enabled=True)
    assert _is_due(src) is True  # last_run_at is None → due

    # ── Case 2: ran 1 minute ago → NOT due (3x = every 8h) ───────────
    src.last_run_at = _iso(now - timedelta(minutes=1))
    assert _is_due(src) is False, "should not be due right after running"

    # ── Case 3: ran 7 hours ago → still NOT due (3x = every 8h) ──────
    src.last_run_at = _iso(now - timedelta(hours=7))
    assert _is_due(src) is False, "should not be due 7h after running on 3x cadence"

    # ── Case 4: ran 9 hours ago → DUE (3x = every 8h) ────────────────
    src.last_run_at = _iso(now - timedelta(hours=9))
    assert _is_due(src) is True, "should be due 9h after running on 3x cadence"

    # ── Case 5: daily cadence, ran 1h ago → NOT due (20h window) ──────
    src.cadence = "daily"
    src.last_run_at = _iso(now - timedelta(hours=1))
    assert _is_due(src) is False, "daily cadence should not be due 1h after running"

    # ── Case 6: daily cadence, ran 25h ago → DUE (>20h window) ───────
    src.last_run_at = _iso(now - timedelta(hours=25))
    assert _is_due(src) is True, "daily cadence should be due 25h after running"

    # ── Case 7: 2x cadence, ran 13h ago → DUE (>12h window) ──────────
    src.cadence = "2x"
    src.last_run_at = _iso(now - timedelta(hours=13))
    assert _is_due(src) is True, "2x cadence should be due 13h after running"

    # ── Case 8: disabled source → never due, regardless of cadence ────
    src.enabled = False
    src.cadence = "3x"
    src.last_run_at = None
    assert _is_due(src) is False, "disabled source should never be due"


def test_is_due_handles_naive_and_aware_timestamps(db_session):
    """last_run_at may be stored as a naive or aware ISO string.

    _is_due must treat them consistently so the scheduler behaves
    the same regardless of how the value was persisted.
    """
    src = SearchSource(name="x", kind="API", category="jobs", cadence="3x", enabled=True)
    now = datetime.now().astimezone()

    # Aware ISO (with timezone offset) — just ran → not due
    src.last_run_at = now.isoformat(timespec="seconds")
    assert _is_due(src) is False

    # Naive ISO (no timezone) — should still be parsed as UTC and not be due
    naive = (now - timedelta(minutes=1)).replace(tzinfo=None).isoformat(timespec="seconds")
    src.last_run_at = naive
    assert _is_due(src) is False, "naive timestamps must be accepted"

    # Garbage value → treated as 'never ran' → due
    src.last_run_at = "not-a-real-date"
    assert _is_due(src) is True