"""Agent 6 — Cover Letter: generate a fact-checked letter per application."""
from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, CoverLetter, Job, MasterProfile
from app.services.profile_lookup import active_profile_for
from app.services.cover_letter import build_cover_letter, write_letter_docx, write_letter_pdf
from app.services.cv_generator import generated_dir

logger = logging.getLogger("careerpilot.cover_letter")


def _active_profile(db: Session, user_id: int | None = None) -> MasterProfile | None:
    """The letter must be built from the applicant's own verified facts."""
    return active_profile_for(db, user_id)


def generate_cover_letter_for_application(db: Session, application: Application,
                                          user_id: int) -> CoverLetter:
    profile = _active_profile(db, application.user_id)
    if profile is None:
        raise ValueError("No active master profile — create it before generating a cover letter")

    if application.job_id is None:
        raise ValueError("Cover letters require an application linked to a job")

    job = db.get(Job, application.job_id)
    if job is None:
        raise ValueError("Linked job no longer exists")

    letter = build_cover_letter(profile, job)
    if not letter.paragraphs:
        raise ValueError(
            "Cover letter blocked by the FactCheck gate: "
            + json.dumps(letter.fact_check.as_dict() if letter.fact_check else {})
        )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = generated_dir() / f"letter_app{application.id}_{stamp}"
    docx_path = write_letter_docx(letter, profile, base.with_suffix(".docx"))
    pdf_path = write_letter_pdf(letter, profile, base.with_suffix(".pdf"))

    row = CoverLetter(
        user_id=user_id,
        application_id=application.id,
        content=letter.text,
        file_path=str(docx_path),
        fact_check_report=json.dumps(letter.fact_check.as_dict() if letter.fact_check else {},
                                     ensure_ascii=False),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    application.cover_letter_id = row.id
    db.commit()
    logger.info("Generated cover letter %d for application %d (fact-checked)",
                row.id, application.id)
    return row
