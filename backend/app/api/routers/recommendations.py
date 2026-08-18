"""Ranked recommendations — top opportunities by priority score (spec §23)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import Job, Scholarship, User
from app.schemas.opportunities import JobOut, ScholarshipOut

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("")
def recommendations(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Top jobs + top scholarships ranked by priority_score (nulls last)."""
    limit = min(max(limit, 1), 50)
    jobs = db.scalars(
        select(Job)
        .where(Job.is_canonical.is_(True), Job.verification_status.notin_(["SUSPICIOUS", "EXPIRED"]))
        .order_by(Job.priority_score.desc().nullslast())
        .limit(limit)
    ).all()
    scholarships = db.scalars(
        select(Scholarship)
        .where(Scholarship.is_canonical.is_(True), Scholarship.verification_status.notin_(["SUSPICIOUS", "EXPIRED"]))
        .order_by(Scholarship.priority_score.desc().nullslast())
        .limit(limit)
    ).all()
    return {
        "jobs": [JobOut.model_validate(j).model_dump() for j in jobs],
        "scholarships": [ScholarshipOut.model_validate(s).model_dump() for s in scholarships],
    }
