"""Batch application preparation (the "review queue").

Prepares several applications in one go so the user's job is reduced to
reviewing and submitting. For each selected opportunity we:

  1. create an Application row owned by the user,
  2. generate a fact-checked CV (services/cv_generator + fact_check gate),
  3. generate a cover letter,
  4. move it to READY FOR REVIEW.

What this deliberately does NOT do is submit anything. Per spec §9 the final
submit is always the user's own action — see application_assistant.py. The
batch exists to remove the preparation work, not the human decision.

Every step is per-application and failure-isolated: one job that cannot be
prepared (missing profile data, FactCheck rejection, bad template) must not
abort the rest of the batch.
"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.agents.cover_letter_agent import generate_cover_letter_for_application
from app.agents.cv_tailor import generate_cv_for_application
from app.core.config import get_settings
from app.models import Application, ApplicationEvent, Job, User

logger = logging.getLogger("careerpilot.batch")

# Opportunities in these states are never worth preparing.
_SKIP_VERIFICATION = {"EXPIRED", "SUSPICIOUS"}

# Statuses that mean "already in the pipeline" — do not duplicate.
_ACTIVE_STATUSES = {
    "SHORTLISTED BY AGENT", "READY FOR REVIEW", "APPROVED",
    "APPLIED", "INTERVIEW", "OFFER",
}

MAX_BATCH = 20


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _event(db: Session, application_id: int, kind: str, description: str) -> None:
    db.add(ApplicationEvent(application_id=application_id, event_type=kind,
                            description=description))


def candidate_jobs(db: Session, user: User, min_score: float, limit: int) -> list[Job]:
    """Highest-priority verified jobs this user has not already queued."""
    already = {
        row.job_id
        for row in db.scalars(
            select(Application).where(Application.user_id == user.id)
        ).all()
        if row.job_id is not None and row.status in _ACTIVE_STATUSES
    }

    jobs = db.scalars(
        select(Job)
        .where(
            Job.is_canonical.is_(True),
            Job.match_score.isnot(None),
            Job.match_score >= min_score,
        )
        .order_by(Job.priority_score.desc().nullslast(), Job.match_score.desc())
        .limit(limit * 4 + 20)      # over-fetch: some are filtered out below
    ).all()

    picked: list[Job] = []
    for job in jobs:
        if job.id in already:
            continue
        if (job.verification_status or "").upper() in _SKIP_VERIFICATION:
            continue
        picked.append(job)
        if len(picked) >= limit:
            break
    return picked


def prepare_application(db: Session, user: User, job: Job) -> dict:
    """Create one application with a CV and cover letter attached."""
    result: dict = {
        "job_id": job.id,
        "title": job.title,
        "organization": job.organization_name,
        "match_score": job.match_score,
        "application_id": None,
        "cv_version_id": None,
        "cover_letter_id": None,
        "status": "FAILED",
        "problems": [],
    }

    application = Application(
        user_id=user.id,
        job_id=job.id,
        status="SHORTLISTED BY AGENT",
        match_score=job.match_score,
        priority_score=job.priority_score,
        deadline=job.deadline,
        date_discovered=_now(),
    )
    db.add(application)
    try:
        db.flush()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Could not create application for job_id=%s", job.id)
        result["problems"].append("Could not create the application row.")
        return result

    result["application_id"] = application.id
    _event(db, application.id, "BATCH_PREPARED", f"Queued from job #{job.id}")

    # ── CV ──────────────────────────────────────────────────────
    try:
        version = generate_cv_for_application(db, application, user.id)
        application.cv_version_id = version.id
        result["cv_version_id"] = version.id
    except ValueError as exc:
        # FactCheck rejection or missing profile data — expected, not a crash.
        result["problems"].append(f"CV: {exc}")
    except Exception:
        logger.exception("CV generation failed for application_id=%s", application.id)
        result["problems"].append("CV: generation failed unexpectedly.")

    # ── Cover letter ────────────────────────────────────────────
    try:
        letter = generate_cover_letter_for_application(db, application, user.id)
        application.cover_letter_id = letter.id
        result["cover_letter_id"] = letter.id
    except ValueError as exc:
        result["problems"].append(f"Cover letter: {exc}")
    except Exception:
        logger.exception("Letter generation failed for application_id=%s", application.id)
        result["problems"].append("Cover letter: generation failed unexpectedly.")

    if application.cv_version_id and application.cover_letter_id:
        application.status = "READY FOR REVIEW"
        _event(db, application.id, "READY_FOR_REVIEW", "CV and cover letter generated")
        result["status"] = "READY FOR REVIEW"
    else:
        # Keep it in the queue but flag it — the user can still review and fix.
        result["status"] = "SHORTLISTED BY AGENT"
        _event(db, application.id, "BATCH_INCOMPLETE", "; ".join(result["problems"])[:400])

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Could not save prepared application for job_id=%s", job.id)
        result["problems"].append("Could not save the prepared application.")
        result["status"] = "FAILED"
    return result


def prepare_batch(db: Session, user: User, limit: int = 5,
                  min_score: float | None = None) -> dict:
    """Prepare up to `limit` applications for review."""
    settings = get_settings()
    threshold = settings.high_match_threshold if min_score is None else min_score
    limit = max(1, min(limit, MAX_BATCH))

    jobs = candidate_jobs(db, user, threshold, limit)
    prepared = [prepare_application(db, user, job) for job in jobs]

    ready = [p for p in prepared if p["status"] == "READY FOR REVIEW"]
    return {
        "requested": limit,
        "min_score": threshold,
        "candidates_found": len(jobs),
        "prepared": len(ready),
        "incomplete": len([p for p in prepared if p["status"] != "READY FOR REVIEW"]),
        "items": prepared,
    }
