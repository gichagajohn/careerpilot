"""Cover letter routes — generate, list, download."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.cover_letter_agent import generate_cover_letter_for_application
from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import Application, CoverLetter, User
from app.schemas.cover_letters import CoverLetterGenerateResult, CoverLetterOut

router = APIRouter(prefix="/cover-letters", tags=["cover-letters"])


@router.get("", response_model=list[CoverLetterOut])
def list_letters(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CoverLetter]:
    return list(
        db.scalars(
            select(CoverLetter).where(CoverLetter.user_id == current_user.id)
            .order_by(CoverLetter.created_at.desc()).limit(50)
        ).all()
    )


@router.post("/applications/{application_id}/generate", response_model=CoverLetterGenerateResult)
def generate_letter(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CoverLetterGenerateResult:
    app_row = db.get(Application, application_id)
    if app_row is None or app_row.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Application not found")
    try:
        row = generate_cover_letter_for_application(db, app_row, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return CoverLetterGenerateResult(
        cover_letter_id=row.id,
        application_id=app_row.id,
        text=row.content or "",
        fact_check=__import__("json").loads(row.fact_check_report or "{}"),
        download_docx=f"/api/v1/cover-letters/{row.id}/download-docx",
        download_pdf=f"/api/v1/cover-letters/{row.id}/download-pdf",
    )


@router.get("/{letter_id}/download-docx")
def download_docx(
    letter_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    row = db.get(CoverLetter, letter_id)
    if row is None or row.user_id != current_user.id or not row.file_path:
        raise HTTPException(status_code=404, detail="Cover letter not found")
    return FileResponse(row.file_path, filename="cover_letter.docx",
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


@router.get("/{letter_id}/download-pdf")
def download_pdf(
    letter_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    row = db.get(CoverLetter, letter_id)
    if row is None or row.user_id != current_user.id or not row.file_path:
        raise HTTPException(status_code=404, detail="Cover letter not found")
    pdf_path = row.file_path.replace(".docx", ".pdf")
    if not __import__("pathlib").Path(pdf_path).exists():
        raise HTTPException(status_code=404, detail="PDF not found for this letter")
    return FileResponse(pdf_path, filename="cover_letter.pdf", media_type="application/pdf")
