"""Cover letter schemas."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CoverLetterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int | None = None
    content: str | None = None
    fact_check_report: str | None = None
    created_at: str


class CoverLetterGenerateResult(BaseModel):
    cover_letter_id: int
    application_id: int
    text: str
    fact_check: dict
    download_docx: str
    download_pdf: str
