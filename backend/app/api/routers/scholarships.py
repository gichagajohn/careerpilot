"""Scholarships routes — CRUD + list with filters."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import Scholarship, User
from app.schemas.opportunities import ScholarshipIn, ScholarshipOut, ScholarshipUpdate

router = APIRouter(prefix="/scholarships", tags=["scholarships"])


@router.get("", response_model=list[ScholarshipOut])
def list_scholarships(
    q: str | None = None,
    verification_status: str | None = None,
    funding_level: str | None = None,
    min_match: float | None = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Scholarship]:
    stmt = select(Scholarship).where(Scholarship.is_canonical.is_(True))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            Scholarship.name.ilike(like)
            | Scholarship.university.ilike(like)
            | Scholarship.programme.ilike(like)
        )
    if verification_status:
        stmt = stmt.where(Scholarship.verification_status == verification_status)
    if funding_level:
        stmt = stmt.where(Scholarship.funding_level.ilike(f"%{funding_level}%"))
    if min_match is not None:
        stmt = stmt.where(Scholarship.match_score >= min_match)
    stmt = stmt.order_by(
        Scholarship.match_score.desc().nullslast(), Scholarship.discovery_date.desc()
    )
    stmt = stmt.limit(min(limit, 500)).offset(max(offset, 0))
    return list(db.scalars(stmt).all())


@router.post("", response_model=ScholarshipOut, status_code=status.HTTP_201_CREATED)
def create_scholarship(
    payload: ScholarshipIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Scholarship:
    item = Scholarship(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/{scholarship_id}", response_model=ScholarshipOut)
def get_scholarship(
    scholarship_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Scholarship:
    item = db.get(Scholarship, scholarship_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Scholarship not found")
    return item


@router.patch("/{scholarship_id}", response_model=ScholarshipOut)
def update_scholarship(
    scholarship_id: int,
    payload: ScholarshipUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Scholarship:
    item = db.get(Scholarship, scholarship_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Scholarship not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item
