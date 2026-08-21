"""Application tracker routes + assistant (Phase 9)."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import (
    Application,
    ApplicationEvent,
    CoverLetter,
    CvVersion,
    Job,
    MasterProfile,
    Scholarship,
    User,
)
from app.schemas.applications import (
    ApplicationIn,
    ApplicationOut,
    ApplicationUpdate,
    BatchPrepResult,
    ReviewItem,
)
from app.services.application_assistant import assist_application
from app.services.batch_prep import prepare_batch

logger = logging.getLogger("careerpilot.applications")

router = APIRouter(prefix="/applications", tags=["applications"])


def _record_event(
    db: Session, application_id: int, event_type: str, description: str | None = None
) -> None:
    db.add(
        ApplicationEvent(
            application_id=application_id,
            event_type=event_type,
            description=description or "",
        )
    )


@router.get("", response_model=list[ApplicationOut])
def list_applications(
    status_filter: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Application]:
    stmt = select(Application).where(Application.user_id == current_user.id)
    if status_filter:
        stmt = stmt.where(Application.status == status_filter)
    stmt = stmt.order_by(
        Application.updated_at.desc().nullslast(), Application.created_at.desc()
    )
    return list(db.scalars(stmt).unique().all())


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
def create_application(
    payload: ApplicationIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Application:
    if payload.job_id is None and payload.scholarship_id is None:
        raise HTTPException(status_code=422, detail="Provide either job_id or scholarship_id")
    if payload.job_id is not None and db.get(Job, payload.job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if payload.scholarship_id is not None and db.get(Scholarship, payload.scholarship_id) is None:
        raise HTTPException(status_code=404, detail="Scholarship not found")
    app = Application(user_id=current_user.id, **payload.model_dump())
    db.add(app)
    db.commit()
    db.refresh(app)
    _record_event(db, app.id, "CREATED", "Application created")
    db.commit()
    db.refresh(app)
    return app


@router.post("/prepare-batch", response_model=BatchPrepResult)
def prepare_batch_endpoint(
    limit: int = 5,
    min_score: float | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BatchPrepResult:
    """Prepare several applications (CV + cover letter) ready for review.

    Nothing is submitted. Each prepared application lands in the review queue
    for the user to read and send themselves.
    """
    stats = prepare_batch(db, current_user, limit=limit, min_score=min_score)
    return BatchPrepResult(**stats)


@router.get("/review-queue", response_model=list[ReviewItem])
def review_queue(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ReviewItem]:
    """Applications prepared and waiting for the user to review and submit."""
    rows = db.scalars(
        select(Application)
        .where(
            Application.user_id == current_user.id,
            Application.status.in_(["SHORTLISTED BY AGENT", "READY FOR REVIEW", "APPROVED"]),
        )
        .order_by(Application.priority_score.desc().nullslast(), Application.id.desc())
    ).all()

    items: list[ReviewItem] = []
    for row in rows:
        job = row.job
        details = (job.match_details or {}) if job is not None else {}
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except ValueError:
                details = {}
        problems = [
            e.description
            for e in row.events
            if e.event_type == "BATCH_INCOMPLETE" and e.description
        ]
        items.append(
            ReviewItem(
                application_id=row.id,
                status=row.status,
                title=job.title if job else None,
                organization=job.organization_name if job else None,
                location=job.location if job else None,
                match_score=row.match_score,
                eligibility=(job.eligibility if job else None),
                deadline=row.deadline,
                apply_url=(job.application_url or job.source_url) if job else None,
                cv_docx=(f"/api/v1/cv/versions/{row.cv_version_id}/download-docx"
                         if row.cv_version_id else None),
                cv_pdf=(f"/api/v1/cv/versions/{row.cv_version_id}/download-pdf"
                        if row.cv_version_id else None),
                letter_docx=(f"/api/v1/cover-letters/{row.cover_letter_id}/download-docx"
                             if row.cover_letter_id else None),
                letter_pdf=(f"/api/v1/cover-letters/{row.cover_letter_id}/download-pdf"
                            if row.cover_letter_id else None),
                strengths=list(details.get("strengths") or [])[:4],
                gaps=list(details.get("gaps") or [])[:4],
                problems=problems,
            )
        )
    return items


@router.get("/{application_id}", response_model=ApplicationOut)
def get_application(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Application:
    app = db.get(Application, application_id)
    if app is None or app.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


@router.patch("/{application_id}", response_model=ApplicationOut)
def update_application(
    application_id: int,
    payload: ApplicationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Application:
    app = db.get(Application, application_id)
    if app is None or app.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Application not found")
    data = payload.model_dump(exclude_unset=True)
    old_status = app.status
    new_status = data.get("status", old_status)
    if old_status != new_status:
        _record_event(db, app.id, "STATUS_CHANGED", f"{old_status} -> {new_status}")
        if new_status == "APPLIED":
            data["date_applied"] = datetime.now().astimezone().isoformat(timespec="seconds")
    for field, value in data.items():
        setattr(app, field, value)
    db.commit()
    db.refresh(app)
    return app


@router.post("/{application_id}/assist")
def assist(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Run the Playwright application assistant — fills non-sensitive fields
    and returns an APPLICATION REVIEW card (spec §9)."""
    app_row = db.get(Application, application_id)
    if app_row is None or app_row.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Application not found")

    profile = db.scalar(
        select(MasterProfile).where(
            MasterProfile.user_id == current_user.id, MasterProfile.is_active.is_(True)
        )
    )
    if profile is None:
        raise HTTPException(status_code=422, detail="No active master profile")

    job = db.get(Job, app_row.job_id) if app_row.job_id else None
    if job is None:
        raise HTTPException(status_code=422, detail="Application has no linked job")

    # Resolve file paths up front — both may be None if no version is linked.
    cv_path: str | None = None
    if app_row.cv_version_id:
        cv = db.get(CvVersion, app_row.cv_version_id)
        if cv:
            cv_path = cv.file_path

    letter_path: str | None = None
    if app_row.cover_letter_id:
        cl = db.get(CoverLetter, app_row.cover_letter_id)
        if cl:
            letter_path = cl.file_path

    try:
        result = asyncio.run(
            assist_application(
                profile,
                current_user.email,
                job.application_url or "",
                cv_path,
                letter_path,
            )
        )
    except Exception as exc:
        logger.exception("Application assistant failed")
        raise HTTPException(status_code=500, detail=f"Assistant error: {exc}") from exc

    if app_row.status != "APPLIED":
        app_row.status = "READY FOR REVIEW"
        db.add(
            ApplicationEvent(
                application_id=app_row.id,
                event_type="ASSISTANT_RUN",
                description=f"Assistant scanned and filled {len(result.get('fields', []))} fields",
            )
        )
        db.commit()

    return result
