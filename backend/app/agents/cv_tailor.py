"""Agent 5 — CV Tailor: generate a tailored, fact-checked CV for an application.

Flow (spec §7, §22):
  application → job → analyze (role type + keywords)
  → build CV from the master profile ONLY → FactCheck gate
  → write .docx + .pdf → store version (cv_versions) with JSON snapshot
    and the fact-check report → link to the application.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_text
from app.models import Application, CvVersion, Job, MasterProfile
from app.services.profile_lookup import active_profile_for
from app.services.cv_generator import build_cv, generated_dir, write_docx, write_pdf

logger = logging.getLogger("careerpilot.cv_tailor")


def _active_profile(db: Session, user_id: int | None = None) -> MasterProfile | None:
    """The CV must be built from the applicant's own verified facts."""
    return active_profile_for(db, user_id)


def generate_cv_for_application(db: Session, application: Application,
                                user_id: int, version_label: str | None = None) -> CvVersion:
    profile = _active_profile(db, application.user_id)
    if profile is None:
        raise ValueError("No active master profile — create it before generating a CV")

    if application.job_id is None:
        raise ValueError("CV generation requires an application linked to a job")

    job = db.get(Job, application.job_id)
    if job is None:
        raise ValueError("Linked job no longer exists")

    cv = build_cv(profile, job)
    if not cv.sections:
        raise ValueError(
            "CV blocked by the FactCheck gate: " + json.dumps(cv.fact_check.as_dict() if cv.fact_check else {})
        )

    # persistence
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = generated_dir() / f"cv_app{application.id}_{stamp}"
    docx_path = write_docx(cv, base.with_suffix(".docx"))
    pdf_path = write_pdf(cv, base.with_suffix(".pdf"))

    snapshot = {
        "target_role": job.title,
        "profile_id": profile.id,
        "profile_phone": decrypt_text(profile.phone_encrypted),
        "sections": cv.sections,
        "fact_check": cv.fact_check.as_dict() if cv.fact_check else {},
    }

    version = CvVersion(
        user_id=user_id,
        application_id=application.id,
        target_role=job.title,
        version_label=version_label or f"v{stamp}",
        file_path=str(docx_path),
        json_snapshot=json.dumps(snapshot, ensure_ascii=False),
        fact_check_report=json.dumps(snapshot["fact_check"], ensure_ascii=False),
    )
    db.add(version)
    db.commit()
    db.refresh(version)

    application.cv_version_id = version.id
    db.commit()
    logger.info("Generated CV %d for application %d (fact-checked, %d claims)",
                version.id, application.id, snapshot["fact_check"].get("total_claims", 0))
    return version
