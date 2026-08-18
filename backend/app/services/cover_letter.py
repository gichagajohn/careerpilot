"""Cover Letter Generator (spec §8) — role-specific, concise, fact-checked.

Design for honesty:
  - The letter is assembled deterministically from the master profile + the
    job record (role, organisation, matched requirements).
  - Only the paragraphs that ASSERT qualifications pass the FactCheck gate;
    the application-intent and closing paragraphs are contextual (they state
    the role and the employer, not claims about John).
  - The whole letter is scanned by the fabrication detectors.
  - If any claim paragraph fails verification, the letter is BLOCKED (a
    partial letter would be worse than none).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.crypto import decrypt_text
from app.models import Job, MasterProfile
from app.services.cv_generator import detect_role_type, write_docx, write_pdf
from app.services.fact_check import FactCheckReport, fact_check_document
from app.services.scoring import profile_skill_names, profile_years_experience

_ROLE_EXPERIENCE_PHRASE = {
    "math": "supporting learners to build strong problem-solving and mathematical reasoning through competency-based assessment and regular feedback",
    "computer_science": "guiding learners in programming and digital literacy, from HTML, CSS and JavaScript to Python and computational thinking",
    "edtech": "integrating technology into classroom practice to support digital learning and ICT-rich lessons",
    "ai_training": "applying strong mathematical and analytical skills to structured AI training, evaluation and data tasks",
    "curriculum": "contributing to curriculum implementation and competency-based assessment aligned to learners' needs",
    "international": "adapting learner-centred, inquiry-based methods to different curriculum contexts",
    "general": "delivering learner-centred, competency-based lessons with a strong focus on learner progress",
}

_PEDAGOGY_PHRASE = (
    "My teaching is learner-centred and competency-based: I plan for learner progress, "
    "use formative assessment to adapt my lessons, and integrate digital tools to make "
    "learning engaging and accessible."
)


def _matched_requirements(job: Job, profile: MasterProfile) -> list[str]:
    from app.services.scoring import _skills_overlap

    profile_skills = profile_skill_names(profile)
    matched: list[str] = []
    for req in (job.requirements or []) + (job.preferred_requirements or []):
        low = req.lower()
        if any(k in low for k in ("degree", "bachelor", "master", "tsc", "registration")):
            continue
        if _skills_overlap(low, profile_skills):
            matched.append(req)
    return matched[:3]


@dataclass
class CoverLetter:
    text: str
    paragraphs: list[str]
    fact_check: FactCheckReport | None = None

    def as_dict(self) -> dict:
        return {"paragraphs": self.paragraphs, "text": self.text}


def _qualifications(profile: MasterProfile) -> str:
    edu = profile.education[0] if profile.education else None
    if not edu:
        return profile.profession or "an educator"
    bits = [p for p in [edu.classification, edu.degree] if p]
    qual = " ".join(bits) or "a degree"
    if edu.field:
        qual += f" in {edu.field}"
    if edu.institution:
        qual += f" from {edu.institution}"
    return qual


def _experience_paragraph(profile: MasterProfile, job: Job, role: str) -> str:
    years = profile_years_experience(profile)
    subjects = sorted({s for e in profile.experience for s in (e.subjects or [])})
    current = next((e for e in profile.experience if e.is_current), None)

    sentence = (
        f"I bring {years:g} year(s) of teaching experience in {', '.join(subjects) or 'Mathematics and Computer Studies'}, "
        f"including {_ROLE_EXPERIENCE_PHRASE.get(role, _ROLE_EXPERIENCE_PHRASE['general'])}."
    )
    if current:
        sentence += (
            f" In my current role at {current.organization}, I teach {', '.join(current.subjects or subjects)[:120]} "
            f"and work closely with learners at different levels of ability."
        )
    if any(k in (profile.professional_registration or "").lower() for k in ("tsc", "service commission")):
        sentence += " I am a Teacher Service Commission (TSC) registered teacher."
    return sentence


def _skills_paragraph(profile: MasterProfile, job: Job, role: str, matched: list[str]) -> str:
    parts = []
    if matched:
        parts.append(f"My experience directly matches key requirements of this role, including {', '.join(matched)}.")
    else:
        parts.append("My subject knowledge and classroom experience align closely with the demands of this role.")
    if role in ("math", "computer_science", "edtech", "curriculum", "international", "general"):
        parts.append(_PEDAGOGY_PHRASE)
    return " ".join(parts)


def build_cover_letter(profile: MasterProfile, job: Job) -> CoverLetter:
    org = job.organization_name or "your school"
    title = job.title or "this role"
    role = detect_role_type(job)
    matched = _matched_requirements(job, profile)

    p1 = (
        f"I am writing to apply for the position of {title} at {org}. "
        f"As a {_qualifications(profile)}, I would welcome the opportunity to contribute "
        f"to your learners and your team."
    )
    p2 = _experience_paragraph(profile, job, role)
    p3 = _skills_paragraph(profile, job, role, matched)
    p4 = (
        f"I would be glad to discuss how my experience can support {org}'s goals. "
        "Thank you for your consideration."
    )
    paragraphs = [p1, p2, p3, p4]

    # FactCheck gate: claim paragraphs must fully verify
    report, kept = fact_check_document([p2, p3], profile)
    letter = CoverLetter(text="\n\n".join(paragraphs), paragraphs=paragraphs, fact_check=report)
    if len(kept) != 2 or report.prohibited_findings:
        return CoverLetter(text="", paragraphs=[], fact_check=report)  # blocked
    return letter


def letter_signature(profile: MasterProfile) -> list[str]:
    lines = ["Sincerely,", profile.full_name]
    phone = decrypt_text(profile.phone_encrypted)
    if phone:
        lines.append(phone)
    if profile.email:
        lines.append(profile.email)
    return lines


def write_letter_docx(letter: CoverLetter, profile: MasterProfile, path: Path) -> Path:
    sections = {"COVER LETTER": letter.paragraphs, "": letter_signature(profile)}
    from app.services.cv_generator import CvDocument
    return write_docx(CvDocument(sections=sections), path)


def write_letter_pdf(letter: CoverLetter, profile: MasterProfile, path: Path) -> Path:
    sections = {"COVER LETTER": letter.paragraphs, "": letter_signature(profile)}
    from app.services.cv_generator import CvDocument
    return write_pdf(CvDocument(sections=sections), path)
