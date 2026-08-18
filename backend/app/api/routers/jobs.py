"""Jobs routes — CRUD + list with filters. Discovery agents (Phase 2) write here."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import Job, JobSource, User
from app.schemas.opportunities import JobIn, JobOut, JobUpdate

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobOut])
def list_jobs(
    q: str | None = None,
    verification_status: str | None = None,
    status_filter: str | None = None,
    min_match: float | None = None,
    remote: bool | None = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Job]:
    stmt = select(Job).where(Job.is_canonical.is_(True))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Job.title.ilike(like) | Job.organization_name.ilike(like))
    if verification_status:
        stmt = stmt.where(Job.verification_status == verification_status)
    if status_filter:
        stmt = stmt.where(Job.status == status_filter)
    if min_match is not None:
        stmt = stmt.where(Job.match_score >= min_match)
    if remote is not None:
        stmt = stmt.where(Job.remote.is_(remote))
    stmt = stmt.order_by(Job.priority_score.desc().nullslast(), Job.discovery_date.desc())
    stmt = stmt.limit(min(limit, 500)).offset(max(offset, 0))
    return list(db.scalars(stmt).unique().all())


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Job:
    job = Job(**payload.model_dump())
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.patch("/{job_id}", response_model=JobOut)
def update_job(
    job_id: int,
    payload: JobUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(job, field, value)
    db.commit()
    db.refresh(job)
    return job


@router.post("/{job_id}/sources", status_code=status.HTTP_201_CREATED)
def add_job_source(
    job_id: int,
    source_type: str,
    source_name: str,
    source_url: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Record an additional listing source for a job (deduplication support)."""
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    exists = db.scalar(
        select(func.count(JobSource.id)).where(
            JobSource.job_id == job_id, JobSource.source_url == source_url
        )
    )
    if exists:
        return {"added": False, "reason": "duplicate source"}
    db.add(
        JobSource(
            job_id=job_id,
            source_type=source_type,
            source_name=source_name,
            source_url=source_url,
        )
    )
    db.commit()
    return {"added": True}
