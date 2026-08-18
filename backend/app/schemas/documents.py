"""Document upload / extraction schemas."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

ExtractionStatus = str  # VERIFIED / UNVERIFIED / USER CONFIRMED


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_name: str
    doc_type: str
    extraction_status: str
    uploaded_at: str
    extractions: list["DocumentExtractionOut"] = []


class DocumentExtractionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    field_name: str
    field_value: str | None = None
    status: str
    created_at: str
