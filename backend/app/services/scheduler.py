"""APScheduler integration — runs discovery agents on a cron.

Default schedules (spec §15):
  - JobScout:         hours 0, 8, 16 local time (3×/day)
  - ScholarshipScout: hours 7, 19 local time (2×/day)
  - Verifier:         every 6 hours (after discovery cycles)
Per-source cadence is additionally enforced inside the agents via
search_sources.last_run_at.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import get_settings
from app.core.db import SessionLocal

logger = logging.getLogger("careerpilot.scheduler")

_scheduler: BackgroundScheduler | None = None


def cron_hour_expr(hours: list[int]) -> str:
    """APScheduler 3.x expects a comma-separated string for cron hour fields."""
    return ",".join(str(h) for h in hours)


def run_jobscout_task() -> None:
    from app.agents.job_scout import run_job_scout

    try:
        with SessionLocal() as db:
            stats = run_job_scout(db)
        logger.info("Scheduled JobScout run finished: %s", stats)
    except Exception:
        logger.exception("Scheduled JobScout run failed")


def run_scholarshipscout_task() -> None:
    from app.agents.scholarship_scout import run_scholarship_scout

    try:
        with SessionLocal() as db:
            stats = run_scholarship_scout(db)
        logger.info("Scheduled ScholarshipScout run finished: %s", stats)
    except Exception:
        logger.exception("Scheduled ScholarshipScout run failed")


def run_verifier_task() -> None:
    from app.agents.matcher import run_matcher_pass
    from app.agents.verifier import run_verification_pass

    try:
        with SessionLocal() as db:
            stats = run_verification_pass(db)
            match_stats = run_matcher_pass(db)  # verify → score → notify (spec pipeline)
        logger.info("Verification + matching pass finished: %s %s", stats, match_stats)
    except Exception:
        logger.exception("Verification/matching pass failed")


def start_scheduler() -> bool:
    """Start the background scheduler (idempotent). Returns True if running."""
    global _scheduler
    settings = get_settings()
    if not settings.enable_scheduler:
        logger.info("Scheduler disabled (ENABLE_SCHEDULER=false)")
        return False
    if _scheduler is not None and _scheduler.running:
        return True

    job_hours = [int(h) for h in settings.jobs_search_hours.split(",") if h.strip().isdigit()]
    if not job_hours:
        job_hours = [0, 8, 16]
    sch_hours = [int(h) for h in settings.scholarship_search_hours.split(",") if h.strip().isdigit()]
    if not sch_hours:
        sch_hours = [7, 19]

    _scheduler = BackgroundScheduler(timezone=settings.timezone)
    _scheduler.add_job(
        run_jobscout_task,
        "cron",
        hour=cron_hour_expr(job_hours),
        id="jobscout",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    _scheduler.add_job(
        run_scholarshipscout_task,
        "cron",
        hour=cron_hour_expr(sch_hours),
        id="scholarshipscout",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    _scheduler.add_job(
        run_verifier_task,
        "cron",
        hour="*/6",  # every 6 hours; runs after discovery cycles
        id="verifier",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    _scheduler.start()
    logger.info(
        "Scheduler started: JobScout at hours %s, ScholarshipScout at hours %s, Verifier every 6h (%s)",
        job_hours, sch_hours, settings.timezone,
    )
    return True


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
    _scheduler = None
