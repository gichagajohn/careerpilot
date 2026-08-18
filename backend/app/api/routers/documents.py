"""Document storage routes.

Uploads are stored under data/uploads (gitignored). PDF/text extraction and
the VERIFIED / UNVERIFIED / USER CONFIRMED workflow arrive with the document
processing phase (Phase 6) — until then extraction_status stays PENDING.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.db import get_db
from app.models import Document, User
from app.schemas.documents import DocumentOut

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".png", ".jpg", ".jpeg"}
ALLOWED_TYPES = {
    "CV", "TRANSCRIPT", "DEGREE", "TSC", "TEACHING_PRACTICE",
    "RECOMMENDATION", "PORTFOLIO", "OTHER",
}


@router.get("", response_model=list[DocumentOut])
def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Document]:
    return list(
        db.scalars(
            select(Document).where(Document.user_id == current_user.id).order_by(Document.uploaded_at.desc())
        ).all()
    )


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    doc_type: str = "OTHER",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    doc_type = doc_type.upper()
    if doc_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=422, detail=f"doc_type must be one of {sorted(ALLOWED_TYPES)}")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422, detail=f"Unsupported file type {suffix or '(none)'}"
        )

    settings = get_settings()
    upload_dir = settings.upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid.uuid4().hex}{suffix}"
    dest = upload_dir / stored_name

    max_bytes = settings.max_upload_mb * 1024 * 1024
    size = 0
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413, detail=f"File exceeds {settings.max_upload_mb} MB limit"
                )
            out.write(chunk)

    doc = Document(
        user_id=current_user.id,
        file_name=file.filename or stored_name,
        file_path=str(dest),
        doc_type=doc_type,
        extraction_status="PENDING",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    doc = db.get(Document, document_id)
    if doc is None or doc.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    doc = db.get(Document, document_id)
    if doc is None or doc.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found")
    Path(doc.file_path).unlink(missing_ok=True)
    db.delete(doc)
    db.commit()
