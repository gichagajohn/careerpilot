"""Agent & search-source routes — manual triggers for discovery and verification."""
from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.job_scout import run_job_scout
from app.agents.matcher import run_matcher_pass
from app.agents.scholarship_scout import run_scholarship_scout
from app.agents.verifier import run_verification_pass
from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import SearchSource, User

router = APIRouter(prefix="/agents", tags=["agents"])


def _split_sources(value: str | None) -> list[str] | None:
    """Parse a comma-separated ``sources`` query param into a list."""
    if not value:
        return None
    names = [part.strip() for part in value.split(",") if part.strip()]
    return names or None


class JobScoutRunResult(BaseModel):
    sources_run: int
    queries_run: int
    listings: int
    filtered_out: int
    new_jobs: int
    duplicates: int
    errors: list[str]


class ScholarshipScoutRunResult(BaseModel):
    sources_run: int
    queries_run: int
    listings: int
    filtered_out: int
    new_scholarships: int
    duplicates: int
    errors: list[str]


class VerificationRunResult(BaseModel):
    jobs_verified: int
    scholarships_verified: int
    expired: int
    suspicious: int
    errors: list[str]


class MatcherRunResult(BaseModel):
    jobs_scored: int
    scholarships_scored: int
    notifications: int
    errors: list[str]


class SearchSourceOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str
    kind: str
    url: str | None = None
    category: str | None = None
    enabled: bool
    cadence: str | None = None
    last_run_at: str | None = None
    notes: str | None = None


@router.post("/jobscout/run", response_model=JobScoutRunResult)
def trigger_jobscout(
    force: bool = True,
    sources: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobScoutRunResult:
    """Manually run the JobScout discovery pipeline (defaults to force=True).

    ``sources`` is an optional comma-separated list of source names
    (e.g. ``remotive,remoteok``). Running one source per request keeps each
    call short, which matters behind hosting proxies that cap request
    duration — a full sweep can otherwise exceed the limit and be killed.
    """
    stats = run_job_scout(db, source_names=_split_sources(sources), force=force)
    return JobScoutRunResult(**stats)


@router.post("/scholarshipscout/run", response_model=ScholarshipScoutRunResult)
def trigger_scholarshipscout(
    force: bool = True,
    sources: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScholarshipScoutRunResult:
    """Manually run the ScholarshipScout discovery pipeline.

    ``sources`` is an optional comma-separated list of source names, so a
    long sweep can be split across several short requests.
    """
    stats = run_scholarship_scout(db, source_names=_split_sources(sources), force=force)
    return ScholarshipScoutRunResult(**stats)


@router.post("/verify/run", response_model=VerificationRunResult)
def trigger_verification(
    entity_type: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VerificationRunResult:
    """Run the verification pass over all UNVERIFIED opportunities.
    entity_type: 'job', 'scholarship', or None (both)."""
    stats = run_verification_pass(db, entity_type=entity_type)
    return VerificationRunResult(**stats)


@router.post("/matcher/run", response_model=MatcherRunResult)
def trigger_matcher(
    entity_type: str | None = None,
    force: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MatcherRunResult:
    """Score opportunities against the master profile (eligibility + priority)."""
    stats = run_matcher_pass(db, entity_type=entity_type, force=force, user_id=current_user.id)
    return MatcherRunResult(**stats)


@router.get("/sources", response_model=list[SearchSourceOut])
def list_sources(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SearchSource]:
    return list(db.scalars(select(SearchSource).order_by(SearchSource.name)).all())


@router.post("/sources/{source_id}/toggle", response_model=SearchSourceOut)
def toggle_source(
    source_id: int,
    enabled: bool,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchSource:
    src = db.get(SearchSource, source_id)
    if src is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    src.enabled = enabled
    db.commit()
    db.refresh(src)
    return src
