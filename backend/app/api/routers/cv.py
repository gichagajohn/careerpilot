"""CV routes — generate, list, view, download."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.cv_tailor import generate_cv_for_application
from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import Application, CvVersion, User
from app.schemas.cv import CvDetail, CvGenerateResult, CvVersionOut

router = APIRouter(prefix="/cv", tags=["cv"])


@router.get("/versions", response_model=list[CvVersionOut])
def list_versions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CvVersion]:
    return list(
        db.scalars(
            select(CvVersion).where(CvVersion.user_id == current_user.id)
            .order_by(CvVersion.created_at.desc()).limit(50)
        ).all()
    )


@router.post("/applications/{application_id}/generate", response_model=CvGenerateResult)
def generate_cv(
    application_id: int,
    version_label: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CvGenerateResult:
    app_row = db.get(Application, application_id)
    if app_row is None or app_row.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Application not found")

    try:
        version = generate_cv_for_application(db, app_row, current_user.id, version_label)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return CvGenerateResult(
        cv_version_id=version.id,
        application_id=app_row.id,
        target_role=version.target_role or "",
        version_label=version.version_label or "",
        summary=json.loads(version.json_snapshot or "{}").get("sections", {}),
        fact_check=json.loads(version.fact_check_report or "{}"),
        download_docx=f"/api/v1/cv/versions/{version.id}/download-docx",
        download_pdf=f"/api/v1/cv/versions/{version.id}/download-pdf",
    )


@router.get("/versions/{version_id}", response_model=CvDetail)
def get_version(
    version_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CvDetail:
    version = db.get(CvVersion, version_id)
    if version is None or version.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="CV version not found")
    return CvDetail(
        id=version.id,
        application_id=version.application_id,
        target_role=version.target_role,
        version_label=version.version_label,
        snapshot=json.loads(version.json_snapshot or "{}"),
        fact_check=json.loads(version.fact_check_report or "{}"),
        created_at=version.created_at,
    )


@router.get("/versions/{version_id}/download-docx")
def download_docx(
    version_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    version = db.get(CvVersion, version_id)
    if version is None or version.user_id != current_user.id or not version.file_path:
        raise HTTPException(status_code=404, detail="CV version not found")
    return FileResponse(version.file_path, filename=f"cv_{version.target_role or 'cv'}.docx",
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


@router.get("/versions/{version_id}/download-pdf")
def download_pdf(
    version_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    version = db.get(CvVersion, version_id)
    if version is None or version.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="CV version not found")
    pdf_path = version.file_path.replace(".docx", ".pdf") if version.file_path else None
    if not pdf_path or not __import__("pathlib").Path(pdf_path).exists():
        raise HTTPException(status_code=404, detail="PDF not found for this version")
    return FileResponse(pdf_path, filename=f"cv_{version.target_role or 'cv'}.pdf",
                        media_type="application/pdf")
