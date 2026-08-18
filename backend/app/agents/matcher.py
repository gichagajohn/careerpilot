"""Agent 4 — Eligibility Analyst & Matcher: scores every opportunity against
the master profile, computes priority ranking and fires notifications.

Pipeline (spec §6, §23):
  profile + opportunity → eligibility 0–100 (rubric) → label
  → relevance (Jaccard) → priority (weighted, configurable)
  → strengths / gaps / risks / missing requirements (deterministic)
  → notifications for high matches and approaching deadlines

The LLM is NOT used here: scores are reproducible and cannot hallucinate.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Job, MasterProfile, Scholarship, Setting
from app.services.notifications import notify_deadline, notify_high_match
from app.services.scoring import (
    DEFAULT_PRIORITY_WEIGHTS,
    career_growth_score,
    compensation_score,
    compute_job_eligibility,
    compute_priority,
    compute_relevance,
    compute_scholarship_eligibility,
    days_until,
    deadline_component,
    org_quality_score,
    scholarship_growth_score,
)

logger = logging.getLogger("careerpilot.matcher")

DEADLINE_REMINDER_DAYS = 3


def _get_weights(db: Session) -> dict[str, float]:
    row = db.scalar(select(Setting).where(Setting.user_id == 0, Setting.key == "priority_weights"))
    if row and row.value:
        try:
            parsed = json.loads(row.value)
            return {**DEFAULT_PRIORITY_WEIGHTS, **parsed}
        except ValueError:
            pass
    return dict(DEFAULT_PRIORITY_WEIGHTS)


def _active_profile(db: Session) -> MasterProfile | None:
    return db.scalar(
        select(MasterProfile).where(MasterProfile.is_active.is_(True)).order_by(MasterProfile.id).limit(1)
    )


def score_job(db: Session, profile: MasterProfile, job: Job, weights: dict[str, float],
              user_id: int | None) -> dict:
    result = compute_job_eligibility(profile, job)
    relevance = compute_relevance(profile, f"{job.title} {job.description or ''} {' '.join(job.requirements or [])}")
    priority = compute_priority(
        eligibility=result.score, relevance=relevance,
        growth=career_growth_score(job),
        compensation=compensation_score(job),
        deadline=deadline_component(job.deadline),
        org=org_quality_score(job.verification_status),
        weights=weights,
    )
    job.match_score = result.score
    job.eligibility = result.label
    job.priority_score = priority
    job.match_details = result.as_dict()

    if user_id is not None:
        threshold = get_settings().high_match_threshold
        if result.score >= threshold:
            notify_high_match(db, user_id, "job", job.id,
                              f"{job.title} @ {job.organization_name or '—'}", result.score)
        if job.deadline:
            days = days_until(job.deadline)
            if days is not None and 0 <= days <= DEADLINE_REMINDER_DAYS:
                notify_deadline(db, user_id, "job", job.id, job.title, job.deadline)
    return result.as_dict()


def score_scholarship(db: Session, profile: MasterProfile, sch: Scholarship,
                      weights: dict[str, float], user_id: int | None) -> dict:
    result = compute_scholarship_eligibility(profile, sch)
    relevance = compute_relevance(profile, f"{sch.name} {sch.programme or ''} {sch.required_field or ''}")
    priority = compute_priority(
        eligibility=result.score, relevance=relevance,
        growth=scholarship_growth_score(sch),
        compensation=compensation_score(sch),
        deadline=deadline_component(sch.deadline),
        org=org_quality_score(sch.verification_status),
        weights=weights,
    )
    sch.match_score = result.score
    sch.eligibility_label = result.label
    sch.priority_score = priority
    sch.match_details = result.as_dict()

    if user_id is not None:
        threshold = get_settings().high_match_threshold
        if result.score >= threshold:
            notify_high_match(db, user_id, "scholarship", sch.id, sch.name, result.score)
        if sch.deadline:
            days = days_until(sch.deadline)
            if days is not None and 0 <= days <= DEADLINE_REMINDER_DAYS:
                notify_deadline(db, user_id, "scholarship", sch.id, sch.name, sch.deadline)
    return result.as_dict()


def run_matcher_pass(db: Session, entity_type: str | None = None, force: bool = False,
                     user_id: int | None = None) -> dict:
    stats = {"jobs_scored": 0, "scholarships_scored": 0, "notifications": 0, "errors": []}

    # Notifications are per-user; the scheduler has no request context, so fall
    # back to the first user (single-user system).
    if user_id is None:
        from app.models import User
        first = db.scalar(select(User).order_by(User.id).limit(1))
        user_id = first.id if first else None

    from sqlalchemy import func
    from app.models import Notification
    notifications_before = db.scalar(select(func.count(Notification.id))) or 0

    profile = _active_profile(db)
    if profile is None:
        stats["errors"].append("No active master profile — cannot score")
        return stats
    weights = _get_weights(db)

    if entity_type in (None, "job"):
        jobs = db.scalars(
            select(Job).where(
                Job.is_canonical.is_(True),
                (Job.match_score.is_(None) if not force else True),
            ).limit(300)
        ).all()
        for job in jobs:
            try:
                score_job(db, profile, job, weights, user_id)
                stats["jobs_scored"] += 1
            except Exception as exc:
                stats["errors"].append(f"job {job.id}: {exc}")
                logger.exception("Scoring failed for job %d", job.id)
        db.commit()

    if entity_type in (None, "scholarship"):
        scholarships = db.scalars(
            select(Scholarship).where(
                Scholarship.is_canonical.is_(True),
                (Scholarship.match_score.is_(None) if not force else True),
            ).limit(300)
        ).all()
        for sch in scholarships:
            try:
                score_scholarship(db, profile, sch, weights, user_id)
                stats["scholarships_scored"] += 1
            except Exception as exc:
                stats["errors"].append(f"scholarship {sch.id}: {exc}")
                logger.exception("Scoring failed for scholarship %d", sch.id)
        db.commit()

    notifications_after = db.scalar(select(func.count(Notification.id))) or 0
    stats["notifications"] = notifications_after - notifications_before
    return stats
