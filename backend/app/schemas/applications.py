"""Application (tracker) schemas."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.opportunities import JobOut, ScholarshipOut

# Statuses per spec §11 — explicit so Pydantic builds a strict Literal.
ApplicationStatus = Literal[
    "DISCOVERED",
    "VERIFIED",
    "SHORTLISTED BY AGENT",
    "READY FOR REVIEW",
    "APPROVED",
    "APPLIED",
    "INTERVIEW",
    "OFFER",
    "REJECTED",
    "WITHDRAWN",
    "EXPIRED",
]


class ApplicationIn(BaseModel):
    job_id: int | None = None
    scholarship_id: int | None = None
    status: ApplicationStatus = "DISCOVERED"
    match_score: float | None = None
    priority_score: float | None = None
    deadline: str | None = None
    salary: str | None = None
    contact_person: str | None = None
    contact_email: str | None = None
    interview_date: str | None = None
    follow_up_date: str | None = None
    outcome: str | None = None
    notes: str | None = None


class ApplicationUpdate(ApplicationIn):
    status: ApplicationStatus | None = None


class ApplicationEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    description: str | None = None
    created_at: str


class ApplicationAnswerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    field_name: str
    question: str | None = None
    answer: str | None = None
    requires_approval: bool
    approved: bool


class ApplicationOut(ApplicationIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date_discovered: str | None = None
    date_applied: str | None = None
    created_at: str
    updated_at: str | None = None
    job: JobOut | None = None
    scholarship: ScholarshipOut | None = None
    events: list[ApplicationEventOut] = []
    answers: list[ApplicationAnswerOut] = []
