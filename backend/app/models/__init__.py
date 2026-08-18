"""SQLAlchemy ORM models — mirrors the schema in docs/01-architecture-proposal.md §5.

All timestamps are ISO-8601 strings in the configured timezone (Africa/Nairobi).
JSON columns store Python lists/dicts and work on both SQLite and PostgreSQL.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


# ══════════ CORE IDENTITY ══════════


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    full_name: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[str] = mapped_column(String, default=_now)
    updated_at: Mapped[str | None] = mapped_column(String, onupdate=_now)

    profiles: Mapped[list["MasterProfile"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    applications: Mapped[list["Application"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class MasterProfile(Base):
    __tablename__ = "master_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    nationality: Mapped[str | None] = mapped_column(String(100))
    location: Mapped[str | None] = mapped_column(String(200))
    phone_encrypted: Mapped[str | None] = mapped_column(Text)  # Fernet-encrypted
    email: Mapped[str | None] = mapped_column(String(320))
    profession: Mapped[str | None] = mapped_column(String(200))
    summary: Mapped[str | None] = mapped_column(Text)
    professional_registration: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(String, default=_now)
    updated_at: Mapped[str | None] = mapped_column(String, onupdate=_now)

    user: Mapped[User] = relationship(back_populates="profiles")
    education: Mapped[list["Education"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", lazy="selectin"
    )
    experience: Mapped[list["Experience"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", lazy="selectin"
    )
    skills: Mapped[list["Skill"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", lazy="selectin"
    )
    certifications: Mapped[list["Certification"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", lazy="selectin"
    )


class Education(Base):
    __tablename__ = "education"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("master_profiles.id"), index=True)
    degree: Mapped[str | None] = mapped_column(String(200))
    institution: Mapped[str | None] = mapped_column(String(200))
    field: Mapped[str | None] = mapped_column(String(200))
    classification: Mapped[str | None] = mapped_column(String(100))  # e.g. First Class Honours
    start_date: Mapped[str | None] = mapped_column(String(20))
    end_date: Mapped[str | None] = mapped_column(String(20))
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)

    profile: Mapped[MasterProfile] = relationship(back_populates="education")


class Experience(Base):
    __tablename__ = "experience"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("master_profiles.id"), index=True)
    organization: Mapped[str | None] = mapped_column(String(200))
    role: Mapped[str | None] = mapped_column(String(200))
    location: Mapped[str | None] = mapped_column(String(200))
    start_date: Mapped[str | None] = mapped_column(String(20))
    end_date: Mapped[str | None] = mapped_column(String(20))
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    subjects: Mapped[list[str] | None] = mapped_column(JSON)  # e.g. ["Mathematics","Computer Studies"]
    grades: Mapped[list[str] | None] = mapped_column(JSON)    # e.g. ["Grade 7","Form 3"]
    description: Mapped[str | None] = mapped_column(Text)

    profile: Mapped[MasterProfile] = relationship(back_populates="experience")


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("master_profiles.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str | None] = mapped_column(String(120))  # teaching / tech / pedagogy ...
    level: Mapped[str | None] = mapped_column(String(40))      # basic / proficient / advanced
    approved: Mapped[bool] = mapped_column(Boolean, default=True)  # 0 = pending user approval
    source: Mapped[str] = mapped_column(String(40), default="USER APPROVED")

    profile: Mapped[MasterProfile] = relationship(back_populates="skills")


class Certification(Base):
    __tablename__ = "certifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("master_profiles.id"), index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    issuer: Mapped[str | None] = mapped_column(String(200))
    date_earned: Mapped[str | None] = mapped_column(String(20))
    reference_number: Mapped[str | None] = mapped_column(Text)

    profile: Mapped[MasterProfile] = relationship(back_populates="certifications")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(Text)
    doc_type: Mapped[str] = mapped_column(String(60))  # CV / transcript / degree / TSC ...
    extraction_status: Mapped[str] = mapped_column(String(20), default="PENDING")
    uploaded_at: Mapped[str] = mapped_column(String, default=_now)

    extractions: Mapped[list["DocumentExtraction"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", lazy="selectin"
    )


class DocumentExtraction(Base):
    __tablename__ = "document_extractions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(120))
    field_value: Mapped[str | None] = mapped_column(Text)
    # NEVER auto-promoted to the master profile until the user confirms.
    status: Mapped[str] = mapped_column(
        String(20), default="UNVERIFIED"
    )  # VERIFIED / UNVERIFIED / USER CONFIRMED
    created_at: Mapped[str] = mapped_column(String, default=_now)

    document: Mapped[Document] = relationship(back_populates="extractions")


# ══════════ ORGANIZATIONS & OPPORTUNITIES ══════════


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    website: Mapped[str | None] = mapped_column(String(500))
    type: Mapped[str | None] = mapped_column(String(120))  # school / university / company ...
    country: Mapped[str | None] = mapped_column(String(100))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"))
    organization_name: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(100))
    employment_type: Mapped[str | None] = mapped_column(String(80))  # Full-time / Part-time / Remote ...
    salary_min: Mapped[float | None] = mapped_column(Float)
    salary_max: Mapped[float | None] = mapped_column(Float)
    salary_currency: Mapped[str | None] = mapped_column(String(10))
    description: Mapped[str | None] = mapped_column(Text)
    requirements: Mapped[list[str] | None] = mapped_column(JSON)  # must-have
    preferred_requirements: Mapped[list[str] | None] = mapped_column(JSON)  # nice-to-have
    deadline: Mapped[str | None] = mapped_column(String(30))
    application_url: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    remote: Mapped[bool] = mapped_column(Boolean, default=False)
    is_international: Mapped[bool] = mapped_column(Boolean, default=False)
    curriculum: Mapped[str | None] = mapped_column(String(100))  # CBC / IGCSE / A-Level / IB ...
    discovery_date: Mapped[str] = mapped_column(String, default=_now)
    verification_status: Mapped[str] = mapped_column(
        String(20), default="UNVERIFIED"
    )  # VERIFIED / LIKELY VERIFIED / UNVERIFIED / SUSPICIOUS / EXPIRED
    verification_notes: Mapped[str | None] = mapped_column(Text)
    duplicate_group: Mapped[str | None] = mapped_column(String(64), index=True)
    is_canonical: Mapped[bool] = mapped_column(Boolean, default=True)
    eligibility: Mapped[str | None] = mapped_column(String(30))  # ELIGIBLE / POSSIBLY / NOT
    match_score: Mapped[float | None] = mapped_column(Float)
    priority_score: Mapped[float | None] = mapped_column(Float)
    is_ai_training: Mapped[bool] = mapped_column(Boolean, default=False)
    match_details: Mapped[dict | None] = mapped_column(JSON)  # strengths/gaps/risks/why-you-match
    status: Mapped[str] = mapped_column(String(30), default="DISCOVERED")
    created_at: Mapped[str] = mapped_column(String, default=_now)
    updated_at: Mapped[str | None] = mapped_column(String, onupdate=_now)

    sources: Mapped[list["JobSource"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", lazy="selectin"
    )


class JobSource(Base):
    """Multiple listing sources for one canonical job (deduplication, spec §24)."""

    __tablename__ = "job_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(40))  # API / RSS / FETCH / SEARCH
    source_name: Mapped[str] = mapped_column(String(120))
    source_url: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[str] = mapped_column(String, default=_now)

    job: Mapped[Job] = relationship(back_populates="sources")


class Scholarship(Base):
    __tablename__ = "scholarships"


    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    university: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(100))
    programme: Mapped[str | None] = mapped_column(String(255))
    degree_level: Mapped[str | None] = mapped_column(String(60))  # Master's
    funding_level: Mapped[str | None] = mapped_column(String(60))  # FULLY FUNDED / PARTIAL ...
    tuition_coverage: Mapped[str | None] = mapped_column(Text)
    accommodation: Mapped[str | None] = mapped_column(Text)
    living_allowance: Mapped[str | None] = mapped_column(Text)
    travel_allowance: Mapped[str | None] = mapped_column(Text)
    insurance: Mapped[str | None] = mapped_column(Text)
    application_fee: Mapped[str | None] = mapped_column(Text)
    eligibility: Mapped[str | None] = mapped_column(Text)
    required_classification: Mapped[str | None] = mapped_column(Text)
    required_field: Mapped[str | None] = mapped_column(Text)
    work_experience_required: Mapped[str | None] = mapped_column(Text)
    english_requirement: Mapped[str | None] = mapped_column(Text)
    age_requirement: Mapped[str | None] = mapped_column(Text)
    deadline: Mapped[str | None] = mapped_column(String(30))
    application_url: Mapped[str | None] = mapped_column(Text)
    official_url: Mapped[str | None] = mapped_column(Text)
    open_to_kenyans: Mapped[bool] = mapped_column(Boolean, default=False)
    open_to_africans: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_status: Mapped[str] = mapped_column(String(20), default="UNVERIFIED")
    verification_notes: Mapped[str | None] = mapped_column(Text)
    match_score: Mapped[float | None] = mapped_column(Float)
    priority_score: Mapped[float | None] = mapped_column(Float)
    eligibility_label: Mapped[str | None] = mapped_column(String(30))
    discovery_date: Mapped[str] = mapped_column(String, default=_now)
    status: Mapped[str] = mapped_column(String(30), default="DISCOVERED")
    duplicate_group: Mapped[str | None] = mapped_column(String(64), index=True)
    is_canonical: Mapped[bool] = mapped_column(Boolean, default=True)
    match_details: Mapped[dict | None] = mapped_column(JSON)  # strengths/gaps/risks/why-you-match
    created_at: Mapped[str] = mapped_column(String, default=_now)
    updated_at: Mapped[str | None] = mapped_column(String, onupdate=_now)

    sources: Mapped[list["ScholarshipSource"]] = relationship(
        back_populates="scholarship", cascade="all, delete-orphan", lazy="selectin"
    )


class ScholarshipSource(Base):
    """Additional listing sources for one canonical scholarship (dedup support)."""

    __tablename__ = "scholarship_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scholarship_id: Mapped[int] = mapped_column(ForeignKey("scholarships.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(40))
    source_name: Mapped[str] = mapped_column(String(120))
    source_url: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[str] = mapped_column(String, default=_now)

    scholarship: Mapped[Scholarship] = relationship(back_populates="sources")


# ══════════ VERIFICATION ══════════


class VerificationResult(Base):
    __tablename__ = "verification_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(40))  # job / scholarship / organization / url
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    check_name: Mapped[str] = mapped_column(String(120))
    passed: Mapped[bool] = mapped_column(Boolean)
    details: Mapped[str | None] = mapped_column(Text)
    result: Mapped[str | None] = mapped_column(String(40))
    checked_at: Mapped[str] = mapped_column(String, default=_now)


# ══════════ APPLICATIONS & TRACKING ══════════

APPLICATION_STATUSES = (
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
)


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"))
    scholarship_id: Mapped[int | None] = mapped_column(ForeignKey("scholarships.id"))
    status: Mapped[str] = mapped_column(String(30), default="DISCOVERED")
    match_score: Mapped[float | None] = mapped_column(Float)
    priority_score: Mapped[float | None] = mapped_column(Float)
    cv_version_id: Mapped[int | None] = mapped_column(ForeignKey("cv_versions.id"))
    cover_letter_id: Mapped[int | None] = mapped_column(ForeignKey("cover_letters.id"))
    deadline: Mapped[str | None] = mapped_column(String(30))
    salary: Mapped[str | None] = mapped_column(String(120))
    contact_person: Mapped[str | None] = mapped_column(String(200))
    contact_email: Mapped[str | None] = mapped_column(String(320))
    date_discovered: Mapped[str | None] = mapped_column(String)
    date_applied: Mapped[str | None] = mapped_column(String)
    interview_date: Mapped[str | None] = mapped_column(String(30))
    follow_up_date: Mapped[str | None] = mapped_column(String(30))
    outcome: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, default=_now)
    updated_at: Mapped[str | None] = mapped_column(String, onupdate=_now)

    user: Mapped[User] = relationship(back_populates="applications")
    job: Mapped[Job | None] = relationship(lazy="joined")
    scholarship: Mapped[Scholarship | None] = relationship(lazy="joined")
    events: Mapped[list["ApplicationEvent"]] = relationship(
        back_populates="application", cascade="all, delete-orphan", lazy="selectin"
    )
    answers: Mapped[list["ApplicationAnswer"]] = relationship(
        back_populates="application", cascade="all, delete-orphan", lazy="selectin"
    )


class ApplicationEvent(Base):
    """Audit trail for every state change on an application."""

    __tablename__ = "application_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(60))  # CREATED / STATUS_CHANGED / REVIEWED ...
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, default=_now)

    application: Mapped[Application] = relationship(back_populates="events")


class ApplicationAnswer(Base):
    __tablename__ = "application_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(120))
    question: Mapped[str | None] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)  # sensitive field
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = mapped_column(String, default=_now)
    updated_at: Mapped[str | None] = mapped_column(String, onupdate=_now)

    application: Mapped[Application] = relationship(back_populates="answers")


class CvVersion(Base):
    __tablename__ = "cv_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    application_id: Mapped[int | None] = mapped_column(Integer)
    target_role: Mapped[str | None] = mapped_column(String(255))
    version_label: Mapped[str | None] = mapped_column(String(80))
    file_path: Mapped[str | None] = mapped_column(Text)
    json_snapshot: Mapped[str | None] = mapped_column(Text)  # exact data used
    fact_check_report: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, default=_now)


class CoverLetter(Base):
    __tablename__ = "cover_letters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    application_id: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[str | None] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(Text)
    fact_check_report: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, default=_now)


# ══════════ INTERVIEWS ══════════


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    interview_date: Mapped[str | None] = mapped_column(String(30))
    format: Mapped[str | None] = mapped_column(String(80))  # in-person / video call ...
    panel: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    questions: Mapped[list["InterviewQuestion"]] = relationship(
        back_populates="interview", cascade="all, delete-orphan", lazy="selectin"
    )


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    interview_id: Mapped[int] = mapped_column(ForeignKey("interviews.id"), index=True)
    category: Mapped[str] = mapped_column(String(60))  # pedagogy / CBE / subject / technical ...
    question: Mapped[str] = mapped_column(Text)
    model_answer: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[str | None] = mapped_column(String(20))

    interview: Mapped[Interview] = relationship(back_populates="questions")


# ══════════ DEADLINES & NOTIFICATIONS ══════════


class Deadline(Base):
    __tablename__ = "deadlines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(40))  # job / scholarship / application
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    due_date: Mapped[str] = mapped_column(String(30))
    reminder_days: Mapped[int] = mapped_column(Integer, default=3)
    notified: Mapped[bool] = mapped_column(Boolean, default=False)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(60))  # HIGH_MATCH_JOB / DEADLINE / INTERVIEW ...
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str | None] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(20), default="IN_APP")
    entity_type: Mapped[str | None] = mapped_column(String(40))  # job / scholarship (dedup key)
    entity_id: Mapped[int | None] = mapped_column(Integer)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_at: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=_now)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    in_app: Mapped[bool] = mapped_column(Boolean, default=True)
    email: Mapped[bool] = mapped_column(Boolean, default=False)
    telegram: Mapped[bool] = mapped_column(Boolean, default=False)
    whatsapp: Mapped[bool] = mapped_column(Boolean, default=False)  # paid, optional Phase 11+
    high_match_job: Mapped[bool] = mapped_column(Boolean, default=True)
    high_eligibility_scholarship: Mapped[bool] = mapped_column(Boolean, default=True)
    deadline_approaching: Mapped[bool] = mapped_column(Boolean, default=True)
    application_ready: Mapped[bool] = mapped_column(Boolean, default=True)
    interview_scheduled: Mapped[bool] = mapped_column(Boolean, default=True)
    followup_due: Mapped[bool] = mapped_column(Boolean, default=True)
    expired: Mapped[bool] = mapped_column(Boolean, default=True)


# ══════════ SEARCH LAYER ══════════


class SearchSource(Base):
    __tablename__ = "search_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(30))  # API / RSS / FETCH / SEARCH
    url: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(60))  # jobs / scholarships
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    cadence: Mapped[str | None] = mapped_column(String(30))
    last_run_at: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(Text)


class SearchRun(Base):
    __tablename__ = "search_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int | None] = mapped_column(Integer)
    query: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[str | None] = mapped_column(String)
    finished_at: Mapped[str | None] = mapped_column(String)
    results_found: Mapped[int] = mapped_column(Integer, default=0)
    new_opportunities: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class ResultCache(Base):
    __tablename__ = "result_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_type: Mapped[str] = mapped_column(String(40))
    query: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    fetched_at: Mapped[str] = mapped_column(String, default=_now)


# ══════════ SETTINGS & TELEMETRY ══════════


class Setting(Base):
    __tablename__ = "settings"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)


class LlmUsageLog(Base):
    __tablename__ = "llm_usage_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str | None] = mapped_column(String(60))
    model: Mapped[str | None] = mapped_column(String(120))
    task: Mapped[str | None] = mapped_column(String(120))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_estimate: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[str] = mapped_column(String, default=_now)
