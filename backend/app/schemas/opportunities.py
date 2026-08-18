"""Opportunity (job / scholarship) schemas — normalized JSON per spec §21."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

VerificationStatus = Literal[
    "VERIFIED", "LIKELY VERIFIED", "UNVERIFIED", "SUSPICIOUS", "EXPIRED"
]
EligibilityLabel = Literal["ELIGIBLE", "POSSIBLY ELIGIBLE", "NOT ELIGIBLE"]


class JobIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    organization_name: str | None = None
    location: str | None = None
    country: str | None = None
    employment_type: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    description: str | None = None
    requirements: list[str] = []
    preferred_requirements: list[str] = []
    deadline: str | None = None
    application_url: str | None = None
    source_url: str | None = None
    remote: bool = False
    is_international: bool = False
    curriculum: str | None = None
    is_ai_training: bool = False
    # Optional at creation (agents may re-score later):
    match_score: float | None = None
    priority_score: float | None = None


class JobUpdate(BaseModel):
    """Partial update — every field optional. Agents PATCH verification/match data."""
    title: str | None = None
    organization_name: str | None = None
    location: str | None = None
    country: str | None = None
    employment_type: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    description: str | None = None
    requirements: list[str] | None = None
    preferred_requirements: list[str] | None = None
    deadline: str | None = None
    application_url: str | None = None
    source_url: str | None = None
    remote: bool | None = None
    is_international: bool | None = None
    curriculum: str | None = None
    is_ai_training: bool | None = None
    verification_status: VerificationStatus | None = None
    verification_notes: str | None = None
    eligibility: EligibilityLabel | None = None
    match_score: float | None = None
    priority_score: float | None = None
    status: str | None = None


class JobOut(JobIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    discovery_date: str
    verification_status: VerificationStatus
    verification_notes: str | None = None
    duplicate_group: str | None = None
    is_canonical: bool
    eligibility: EligibilityLabel | None = None
    match_score: float | None = None
    priority_score: float | None = None
    match_details: dict | None = None
    status: str
    created_at: str
    updated_at: str | None = None
    sources: list["JobSourceOut"] = []


class JobSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_type: str
    source_name: str
    source_url: str | None = None
    fetched_at: str


class ScholarshipIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    university: str | None = None
    country: str | None = None
    programme: str | None = None
    degree_level: str | None = None
    funding_level: str | None = None
    tuition_coverage: str | None = None
    accommodation: str | None = None
    living_allowance: str | None = None
    travel_allowance: str | None = None
    insurance: str | None = None
    application_fee: str | None = None
    eligibility: str | None = None
    required_classification: str | None = None
    required_field: str | None = None
    work_experience_required: str | None = None
    english_requirement: str | None = None
    age_requirement: str | None = None
    deadline: str | None = None
    application_url: str | None = None
    official_url: str | None = None
    open_to_kenyans: bool = False
    open_to_africans: bool = False
    # Optional at creation:
    match_score: float | None = None


class ScholarshipUpdate(BaseModel):
    """Partial update — every field optional."""
    name: str | None = None
    university: str | None = None
    country: str | None = None
    programme: str | None = None
    degree_level: str | None = None
    funding_level: str | None = None
    tuition_coverage: str | None = None
    accommodation: str | None = None
    living_allowance: str | None = None
    travel_allowance: str | None = None
    insurance: str | None = None
    application_fee: str | None = None
    eligibility: str | None = None
    required_classification: str | None = None
    required_field: str | None = None
    work_experience_required: str | None = None
    english_requirement: str | None = None
    age_requirement: str | None = None
    deadline: str | None = None
    application_url: str | None = None
    official_url: str | None = None
    open_to_kenyans: bool | None = None
    open_to_africans: bool | None = None
    verification_status: VerificationStatus | None = None
    verification_notes: str | None = None
    eligibility_label: EligibilityLabel | None = None
    match_score: float | None = None
    status: str | None = None


class ScholarshipOut(ScholarshipIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    verification_status: VerificationStatus
    verification_notes: str | None = None
    eligibility_label: EligibilityLabel | None = None
    match_score: float | None = None
    priority_score: float | None = None
    match_details: dict | None = None
    discovery_date: str
    status: str
    duplicate_group: str | None = None
    is_canonical: bool
    created_at: str
    updated_at: str | None = None
