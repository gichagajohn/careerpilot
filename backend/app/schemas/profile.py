"""Master profile schemas.

IMPORTANT (anti-fabrication): the master profile is the single source of
truth for every generated document. Fields here are written only by the
user (or via user-confirmed document extractions).
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class EducationIn(BaseModel):
    degree: str | None = None
    institution: str | None = None
    field: str | None = None
    classification: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    notes: str | None = None


class EducationOut(EducationIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ExperienceIn(BaseModel):
    organization: str | None = None
    role: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    subjects: list[str] = []
    grades: list[str] = []
    description: str | None = None


class ExperienceOut(ExperienceIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class SkillIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: str | None = None
    level: str | None = None


class SkillOut(SkillIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    approved: bool
    source: str


class CertificationIn(BaseModel):
    name: str | None = None
    issuer: str | None = None
    date_earned: str | None = None
    reference_number: str | None = None


class CertificationOut(CertificationIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class MasterProfileIn(BaseModel):
    full_name: str | None = None
    nationality: str | None = None
    location: str | None = None
    phone: str | None = None  # encrypted at rest
    email: str | None = None
    profession: str | None = None
    summary: str | None = None
    professional_registration: str | None = None


class MasterProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    nationality: str | None = None
    location: str | None = None
    phone: str | None = None  # decrypted for the authenticated owner only
    email: str | None = None
    profession: str | None = None
    summary: str | None = None
    professional_registration: str | None = None
    education: list[EducationOut] = []
    experience: list[ExperienceOut] = []
    skills: list[SkillOut] = []
    certifications: list[CertificationOut] = []
    # False for a freshly created, not-yet-filled profile → the dashboard
    # shows the first-time setup form instead of an empty read-only card.
    profile_complete: bool = False
