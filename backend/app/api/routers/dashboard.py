"""Dashboard summary route."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import Application, Job, Scholarship, User
from app.schemas.dashboard import DashboardSummary, UpcomingDeadline

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardSummary:
    now = datetime.now().astimezone()
    week_ago = (now - timedelta(days=7)).isoformat(timespec="seconds")
    in_two_weeks_date = (now + timedelta(days=14)).date()

    total_opportunities = (
        db.scalar(select(func.count(Job.id)).where(Job.is_canonical.is_(True))) or 0
    ) + (
        db.scalar(select(func.count(Scholarship.id)).where(Scholarship.is_canonical.is_(True)))
        or 0
    )
    new_opportunities = (
        db.scalar(
            select(func.count(Job.id)).where(
                Job.is_canonical.is_(True), Job.discovery_date >= week_ago
            )
        )
        or 0
    ) + (
        db.scalar(
            select(func.count(Scholarship.id)).where(
                Scholarship.is_canonical.is_(True), Scholarship.discovery_date >= week_ago
            )
        )
        or 0
    )
    high_match = (
        db.scalar(
            select(func.count(Job.id)).where(
                Job.is_canonical.is_(True), Job.match_score >= 80
            )
        )
        or 0
    ) + (
        db.scalar(
            select(func.count(Scholarship.id)).where(
                Scholarship.is_canonical.is_(True), Scholarship.match_score >= 80
            )
        )
        or 0
    )
    scholarships_total = (
        db.scalar(select(func.count(Scholarship.id)).where(Scholarship.is_canonical.is_(True)))
        or 0
    )

    # Opportunities are a shared discovery pool, but applications belong to a
    # single user and must never be counted across accounts.
    apps = db.scalars(
        select(Application).where(Application.user_id == current_user.id)
    ).all()
    apps_total = len(apps)
    apps_interviews = sum(1 for a in apps if a.status == "INTERVIEW")
    apps_offers = sum(1 for a in apps if a.status == "OFFER")

    upcoming: list[UpcomingDeadline] = []
    jobs = db.scalars(
        select(Job).where(Job.is_canonical.is_(True), Job.deadline.isnot(None))
    ).all()
    for job in jobs:
        try:
            due = datetime.fromisoformat(job.deadline).date()
        except ValueError:
            continue
        if now.date() <= due <= in_two_weeks_date:
            upcoming.append(
                UpcomingDeadline(
                    kind="job",
                    title=job.title,
                    organization=job.organization_name,
                    due_date=job.deadline,
                    link_id=job.id,
                )
            )
    scholarships = db.scalars(
        select(Scholarship).where(Scholarship.deadline.isnot(None))
    ).all()
    for sch in scholarships:
        try:
            due = datetime.fromisoformat(sch.deadline).date()
        except ValueError:
            continue
        if now.date() <= due <= in_two_weeks_date:
            upcoming.append(
                UpcomingDeadline(
                    kind="scholarship",
                    title=sch.name,
                    organization=sch.university,
                    due_date=sch.deadline,
                    link_id=sch.id,
                )
            )
    upcoming.sort(key=lambda d: d.due_date)

    return DashboardSummary(
        total_opportunities=total_opportunities,
        new_opportunities=new_opportunities,
        high_match_opportunities=high_match,
        applications_total=apps_total,
        applications_interviews=apps_interviews,
        applications_offers=apps_offers,
        scholarships_total=scholarships_total,
        upcoming_deadlines=upcoming,
    )
