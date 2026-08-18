"""Notification schemas."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    title: str
    body: str | None = None
    channel: str
    is_read: bool
    entity_type: str | None = None
    entity_id: int | None = None
    created_at: str


class NotificationPrefsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    in_app: bool
    email: bool
    telegram: bool
    whatsapp: bool
    high_match_job: bool
    high_eligibility_scholarship: bool
    deadline_approaching: bool
    application_ready: bool
    interview_scheduled: bool
    followup_due: bool
    expired: bool


class NotificationPrefsIn(BaseModel):
    email: bool | None = None
    telegram: bool | None = None
    high_match_job: bool | None = None
    high_eligibility_scholarship: bool | None = None
    deadline_approaching: bool | None = None
    application_ready: bool | None = None
    interview_scheduled: bool | None = None
    followup_due: bool | None = None
    expired: bool | None = None
