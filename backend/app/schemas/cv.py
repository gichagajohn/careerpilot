"""CV schemas."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CvVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int | None = None
    target_role: str | None = None
    version_label: str | None = None
    file_path: str | None = None
    created_at: str


class CvGenerateResult(BaseModel):
    cv_version_id: int
    application_id: int
    target_role: str
    version_label: str
    summary: dict
    fact_check: dict
    download_docx: str
    download_pdf: str


class CvDetail(BaseModel):
    id: int
    application_id: int | None = None
    target_role: str | None = None
    version_label: str | None = None
    snapshot: dict
    fact_check: dict
    created_at: str
