"""Eligibility Analyst — deterministic 100-pt scoring (spec §6).

Weights (spec):
  Jobs:        Education 20 · Subject match 20 · Experience 20 ·
               Technical skills 15 · Registration 10 · Location 10 · Other 5
  Scholarships: Education 25 · Field 20 · Classification 15 · English 10 ·
               Work experience 10 · Kenya/Africa-open 10 · Age/other 10

Everything is computed from the master profile (single source of truth) and
the opportunity record. Scores are reproducible and testable; the LLM is NOT
used here, so nothing can be hallucinated.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from dateutil import parser as dtparser

from app.core.config import get_settings
from app.models import Job, MasterProfile, Scholarship
from app.schemas.opportunities import EligibilityLabel

# ── subject normalisation ──────────────────────────────────────
SUBJECT_SYNONYMS: dict[str, set[str]] = {
    "mathematics": {"mathematics", "math", "maths", "mathematical"},
    "computer_studies": {"computer studies", "computer science", "computing", "cs", "ict", "information technology", "information communication technology"},
    "integrated_science": {"integrated science", "general science"},
    "physics": {"physics"},
    "chemistry": {"chemistry"},
    "biology": {"biology", "life science"},
    "english": {"english"},
    "kiswahili": {"kiswahili", "swahili"},
    "stem": {"stem", "steam"},
}

SUBJECT_KEYWORDS = sorted({w for s in SUBJECT_SYNONYMS.values() for w in s}, key=len, reverse=True)

PROFILE_SUBJECTS = {"mathematics", "computer_studies", "integrated_science", "ict", "stem"}


def _parse_date(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return dtparser.parse(text, fuzzy=True)
    except (dtparser.ParserError, ValueError):
        return None


def days_until(text: str | None) -> int | None:
    """Whole days until a deadline (negative = past); None if unparseable."""
    dt = _parse_date(text)
    if dt is None:
        return None
    now = datetime.now() if dt.tzinfo is None else datetime.now().astimezone()
    return (dt - now).days


# ── results ────────────────────────────────────────────────────


@dataclass
class EligibilityResult:
    score: float
    label: EligibilityLabel
    components: dict[str, float] = field(default_factory=dict)   # component → points earned
    max_components: dict[str, float] = field(default_factory=dict)  # component → max points
    strengths: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    missing_requirements: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "score": round(self.score, 1),
            "label": self.label,
            "components": self.components,
            "strengths": self.strengths,
            "gaps": self.gaps,
            "risks": self.risks,
            "missing_requirements": self.missing_requirements,
        }


# ── profile helpers ────────────────────────────────────────────


def profile_skill_names(profile: MasterProfile) -> set[str]:
    return {s.name.lower().strip() for s in profile.skills if s.approved}


def profile_years_experience(profile: MasterProfile) -> float:
    """Total months of experience from profile entries (current roles → now)."""
    months = 0.0
    for exp in profile.experience:
        start = _parse_date(exp.start_date)
        if start is None:
            continue
        end = _parse_date(exp.end_date) or datetime.now()
        # normalize naive/aware so comparisons never fail
        if start.tzinfo is not None:
            start = start.replace(tzinfo=None)
        if end.tzinfo is not None:
            end = end.replace(tzinfo=None)
        if end < start:
            continue
        months += max((end - start).days, 0) / 30.44
    return round(months / 12, 1)


def _subjects_in_text(text: str) -> set[str]:
    found: set[str] = set()
    low = (text or "").lower()
    for key, syns in SUBJECT_SYNONYMS.items():
        for s in syns:
            if re.search(rf"\b{re.escape(s)}\b", low):
                found.add(key)
                break
    return found


def _covered_subjects(job_text: str, profile: MasterProfile) -> tuple[set[str], set[str]]:
    job_subjects = _subjects_in_text(job_text)
    if not job_subjects:
        return set(), set()
    profile_subjects = set(PROFILE_SUBJECTS)  # from the master profile (seed)
    for exp in profile.experience:
        for s in exp.subjects or []:
            for key, syns in SUBJECT_SYNONYMS.items():
                if any(x in s.lower() for x in syns):
                    profile_subjects.add(key)
    covered = job_subjects & profile_subjects
    return job_subjects, covered


def _required_years(text: str | None) -> float | None:
    if not text:
        return None
    patterns = [
        r"(\d+)\+?\s*(?:years?|yrs?)[^.]{0,60}(?:experience|teaching)",
        r"(?:experience|teaching)[^.]{0,60}(\d+)\+?\s*(?:years?|yrs?)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            return float(m.group(1))
    return None


# ── job eligibility ────────────────────────────────────────────


def _education_score(job: Job, profile: MasterProfile) -> tuple[float, list[str], list[str]]:
    text = f"{job.title} {job.description or ''}".lower()
    gaps: list[str] = []
    strengths: list[str] = []
    has_degree = bool(profile.education)
    for e in profile.education:
        if e.degree:
            strengths.append(f"{e.degree}{(' — ' + e.classification) if e.classification else ''}")

    if re.search(r"\bph\.?\s?d\b", text):
        gaps.append("PhD required — not in profile")
        return 4.0, strengths, gaps
    if re.search(r"\bmaster'?s\b|masters degree", text):
        gaps.append("Master's degree required — profile holds a Bachelor's")
        return 8.0, strengths, gaps
    if not has_degree:
        gaps.append("Degree required but none in profile")
        return 5.0, strengths, gaps
    # Bachelor's (or unspecified) → field relevance matters
    job_subjects, covered = _covered_subjects(text, profile)
    if job_subjects and not covered:
        gaps.append("Degree field does not clearly match the required subjects")
        return 15.0, strengths, gaps
    return 20.0, strengths, gaps


def _experience_score(job: Job, profile: MasterProfile) -> tuple[float, list[str], list[str]]:
    text = f"{job.title} {job.description or ''}"
    required = _required_years(text)
    have = profile_years_experience(profile)
    strengths: list[str] = []
    gaps: list[str] = []
    if have > 0:
        strengths.append(f"{have:g} year(s) of teaching experience on record")
    if required is None:
        return 20.0, strengths, gaps
    if have >= required:
        return 20.0, strengths, gaps
    gaps.append(f"{required:g} year(s) of experience required; {have:g} on record")
    return round(20.0 * have / required, 1), strengths, gaps


_OTHER_COMPONENT_KEYWORDS = (
    "degree", "bachelor", "master", "phd", "tsc", "registration",
    "teacher service commission", "ielts", "toefl", "safeguarding", "first aid",
)


def _skills_overlap(req_low: str, profile_skills: set[str]) -> bool:
    """True if a profile skill appears in the requirement, or shares >=70% tokens."""
    req_tokens = set(re.findall(r"[a-z0-9]+", req_low))
    if not req_tokens:
        return False
    for sk in profile_skills:
        if len(sk) < 3:
            continue
        if sk in req_low:
            return True
        sk_tokens = set(re.findall(r"[a-z0-9]+", sk))
        if sk_tokens and len(sk_tokens & req_tokens) / len(sk_tokens) >= 0.7:
            return True
    return False


def _skills_score(job: Job, profile: MasterProfile) -> tuple[float, list[str], list[str]]:
    profile_skills = profile_skill_names(profile)
    strengths: list[str] = []
    gaps: list[str] = []
    candidates = (job.requirements or []) + (job.preferred_requirements or [])
    if not candidates:
        return 15.0, strengths, gaps

    matched: list[str] = []
    unmatched: list[str] = []
    for req in candidates:
        low = req.lower()
        # requirements handled by other rubric components (education, registration,
        # english, certificates) should not be double-counted here
        if any(k in low for k in _OTHER_COMPONENT_KEYWORDS):
            continue
        if _skills_overlap(low, profile_skills):
            matched.append(req)
        else:
            unmatched.append(req)

    required_count = len(job.requirements or [])
    if required_count and matched:
        strengths.append(f"Skills match: {', '.join(matched[:3])}")
    for u in unmatched[:3]:
        gaps.append(f"Requirement not covered by profile: {u}")

    denom = required_count or len(candidates)
    score = round(15.0 * len(matched) / max(denom, 1), 1)
    return score, strengths, gaps


def _registration_score(job: Job, profile: MasterProfile) -> tuple[float, list[str], list[str]]:
    text = f"{job.title} {job.description or ''}".lower()
    strengths: list[str] = []
    gaps: list[str] = []
    reg = (profile.professional_registration or "").lower()
    if re.search(r"\btsc\b|teacher.?registration|teachers service commission", text):
        if "tsc" in reg or "teacher" in reg and "service commission" in reg:
            strengths.append("TSC-registered teacher")
            return 10.0, strengths, gaps
        gaps.append("Professional registration (TSC) required")
        return 0.0, strengths, gaps
    return 10.0, strengths, gaps


def _location_score(job: Job, profile: MasterProfile) -> tuple[float, list[str], list[str]]:
    text = f"{job.title} {job.description or ''} {job.location or ''}".lower()
    gaps: list[str] = []
    strengths: list[str] = []
    if job.remote or "remote" in text or "work from home" in text:
        strengths.append("Remote-friendly role")
        return 10.0, strengths, gaps
    if (job.country and job.country.lower() == "kenya") or "kenya" in text or "nairobi" in text:
        strengths.append("Located in Kenya (Nairobi)")
        return 10.0, strengths, gaps
    if get_settings().open_to_international:
        gaps.append("International location — requires relocation")
        return 6.0, strengths, gaps
    gaps.append("International/overseas location — relocation not indicated in profile")
    return 0.0, strengths, gaps


def _other_score(job: Job, profile: MasterProfile) -> tuple[float, list[str], list[str]]:
    """Hard certifications/language requirements not covered elsewhere."""
    text = f"{job.title} {job.description or ''} {' '.join(job.requirements or [])}".lower()
    gaps: list[str] = []
    missing: list[str] = []
    score = 5.0
    checks = [
        (r"\bielts\b|\btoefl\b", "English certificate (IELTS/TOEFL) not in profile"),
        (r"\bsafeguarding\b", "Safeguarding certificate not in profile"),
        (r"\bfirst[- ]?aid\b", "First-aid certificate not in profile"),
        (r"\bcpr\b", "CPR certification not in profile"),
    ]
    for pattern, gap_text in checks:
        if re.search(pattern, text):
            missing.append(gap_text)
            gaps.append(gap_text)
            score = max(score - 1.5, 0.0)
    return score, [], gaps


def eligibility_label(score: float) -> EligibilityLabel:
    s = get_settings()
    if score >= s.eligibility_eligible_threshold:
        return "ELIGIBLE"
    if score >= s.eligibility_possible_threshold:
        return "POSSIBLY ELIGIBLE"
    return "NOT ELIGIBLE"


def compute_job_eligibility(profile: MasterProfile, job: Job) -> EligibilityResult:
    max_comp = {"education": 20, "subject_match": 20, "experience": 20,
                "skills": 15, "registration": 10, "location": 10, "other": 5}

    edu_score, edu_strengths, edu_gaps = _education_score(job, profile)
    exp_score, exp_strengths, exp_gaps = _experience_score(job, profile)
    skill_score, skill_strengths, skill_gaps = _skills_score(job, profile)
    reg_score, reg_strengths, reg_gaps = _registration_score(job, profile)
    loc_score, loc_strengths, loc_gaps = _location_score(job, profile)
    other_score, other_strengths, other_gaps = _other_score(job, profile)

    job_subjects, covered = _covered_subjects(f"{job.title} {job.description or ''}", profile)
    if job_subjects:
        subject_score = round(20.0 * len(covered) / len(job_subjects), 1)
        if subject_score < 20 and covered:
            missing_subj = job_subjects - covered
            other_gaps.append(f"Subjects not covered by profile: {', '.join(sorted(missing_subj))}")
    else:
        subject_score = 20.0

    components = {
        "education": edu_score, "subject_match": subject_score, "experience": exp_score,
        "skills": skill_score, "registration": reg_score, "location": loc_score, "other": other_score,
    }
    total = round(sum(components.values()), 1)

    risks: list[str] = []
    if job.verification_status in ("SUSPICIOUS", "EXPIRED"):
        risks.append(f"Verification status: {job.verification_status}")
    elif job.verification_status != "VERIFIED":
        risks.append(f"Not yet fully verified ({job.verification_status})")
    if not job.salary_min and not job.salary_max:
        risks.append("Salary not disclosed")
    if job.deadline:
        days = days_until(job.deadline)
        if days is not None:
            if days < 0:
                risks.append("Deadline already passed")
            elif days <= 7:
                risks.append(f"Deadline in {days} day(s) — apply soon")

    strengths = dedupe(edu_strengths + exp_strengths + skill_strengths + reg_strengths + loc_strengths + other_strengths)
    gaps = dedupe(edu_gaps + exp_gaps + skill_gaps + reg_gaps + loc_gaps + other_gaps)
    missing = [g for g in gaps if "not in profile" in g or "not covered" in g or "required" in g]

    return EligibilityResult(
        score=total, label=eligibility_label(total),
        components=components, max_components=max_comp,
        strengths=strengths[:6], gaps=gaps[:6], risks=risks[:4],
        missing_requirements=missing[:6],
    )


# ── scholarship eligibility ────────────────────────────────────


def compute_scholarship_eligibility(profile: MasterProfile, sch: Scholarship) -> EligibilityResult:
    max_comp = {"education": 25, "field": 20, "classification": 15,
                "english": 10, "experience": 10, "kenya_africa": 10, "age": 10}
    gaps: list[str] = []
    strengths: list[str] = []

    # education
    has_bachelor = any(e.degree and "bachelor" in e.degree.lower() for e in profile.education)
    if has_bachelor:
        strengths.append("Bachelor's degree held (scholarships typically require one)")
        education = 25.0
    else:
        gaps.append("No Bachelor's degree in profile")
        education = 8.0

    # field
    required_field = (sch.required_field or sch.programme or "") + " " + (sch.name or "")
    req_subjects = _subjects_in_text(required_field)
    if not req_subjects:
        field = 20.0
    else:
        profile_subjects = PROFILE_SUBJECTS | {"data_science", "ai", "ict"}
        covered = req_subjects & profile_subjects
        field = round(20.0 * len(covered) / len(req_subjects), 1)
        if field < 20:
            gaps.append(f"Programme fields not covered by profile: {', '.join(sorted(req_subjects - covered))}")

    # classification
    req_class = (sch.required_classification or "").lower()
    profile_class = " ".join((e.classification or "") for e in profile.education).lower()
    if not req_class:
        classification = 15.0
    elif "first class" in profile_class or ("upper" in req_class and "upper second" in profile_class):
        strengths.append("First Class Honours meets the required classification")
        classification = 15.0
    else:
        gaps.append(f"Required classification ({sch.required_classification}) not confirmed in profile")
        classification = 4.0

    # english
    if sch.english_requirement:
        gaps.append(f"English requirement ({sch.english_requirement}) — no score on file")
        english = 5.0
    else:
        english = 10.0

    # work experience
    req_exp = _required_years(sch.work_experience_required or sch.eligibility or "")
    have = profile_years_experience(profile)
    if req_exp is None:
        experience = 10.0
    elif have >= req_exp:
        experience = 10.0
    else:
        gaps.append(f"{req_exp:g} year(s) experience required; {have:g} on record")
        experience = round(10.0 * have / req_exp, 1)

    # kenya / africa openness
    if sch.open_to_kenyans:
        strengths.append("Explicitly open to Kenyan applicants")
        kenya_africa = 10.0
    elif sch.open_to_africans:
        strengths.append("Open to African applicants")
        kenya_africa = 10.0
    elif sch.eligibility and ("international" in sch.eligibility.lower()):
        kenya_africa = 6.0
    else:
        kenya_africa = 6.0  # unknown → partial

    # age
    if sch.age_requirement:
        gaps.append(f"Age requirement ({sch.age_requirement}) — not verifiable from profile")
        age = 5.0
    else:
        age = 10.0

    components = {"education": education, "field": field, "classification": classification,
                  "english": english, "experience": experience, "kenya_africa": kenya_africa, "age": age}
    total = round(sum(components.values()), 1)

    risks: list[str] = []
    if sch.funding_level == "FULLY FUNDED":
        strengths.append("Fully funded (official evidence on file)")
    elif sch.funding_level == "UNSPECIFIED":
        risks.append("Funding level not yet confirmed")
    if sch.deadline:
        days = days_until(sch.deadline)
        if days is not None:
            if days < 0:
                risks.append("Deadline already passed")
            elif days <= 30:
                risks.append(f"Deadline in {days} day(s)")

    return EligibilityResult(
        score=total, label=eligibility_label(total),
        components=components, max_components=max_comp,
        strengths=dedupe(strengths)[:6], gaps=dedupe(gaps)[:6], risks=risks[:4],
        missing_requirements=[g for g in gaps if "not" in g][:6],
    )


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for i in items:
        if i and i not in seen:
            seen.add(i)
            out.append(i)
    return out


# ── relevance & priority ───────────────────────────────────────


def _token_set(text: str | None) -> set[str]:
    if not text:
        return set()
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def compute_relevance(profile: MasterProfile, text: str | None) -> float:
    """Jaccard overlap between opportunity text and the profile's own words."""
    profile_words = _token_set(
        " ".join(e.field or "" for e in profile.education)
        + " " + " ".join(e.degree or "" for e in profile.education)
        + " " + " ".join(s.name for s in profile.skills)
        + " " + " ".join(" ".join(e.subjects or []) for e in profile.experience)
    )
    opp_words = _token_set(text)
    if not opp_words:
        return 0.0
    return round(100.0 * len(profile_words & opp_words) / len(opp_words | profile_words), 1)


def career_growth_score(job: Job) -> float:
    s = 0.5
    title = (job.title or "").lower()
    if job.is_ai_training:
        s += 0.2
    if job.is_international:
        s += 0.15
    if any(k in title for k in ("senior", "lead", "head", "director", "coordinator")):
        s += 0.15
    if any(k in title for k in ("curriculum", "instructional", "edtech")):
        s += 0.1
    if job.remote:
        s += 0.05
    return round(min(s, 1.0), 2)


def scholarship_growth_score(sch: Scholarship) -> float:
    funding = {
        "FULLY FUNDED": 0.9, "TUITION-FREE": 0.8, "TUITION-ONLY": 0.6, "PARTIAL": 0.6,
    }.get((sch.funding_level or "").upper(), 0.5)
    return round(min(funding + 0.1, 1.0), 2)


def compensation_score(job_or_sch) -> float:
    if isinstance(job_or_sch, Scholarship):
        return scholarship_growth_score(job_or_sch)  # funding acts as compensation
    job = job_or_sch
    if job.salary_min or job.salary_max:
        return 0.8
    if job.description and "competitive salary" in job.description.lower():
        return 0.6
    return 0.5


def deadline_component(deadline: str | None) -> float:
    days = days_until(deadline)
    if days is None:
        return 0.5
    if days < 0:
        return 0.0
    if days <= 3:
        return 0.2
    if days <= 7:
        return 0.5
    if days <= 30:
        return 0.9
    return 0.8


def org_quality_score(verification_status: str | None) -> float:
    return {
        "VERIFIED": 1.0, "LIKELY VERIFIED": 0.8, "UNVERIFIED": 0.5,
        "SUSPICIOUS": 0.0, "EXPIRED": 0.0,
    }.get(verification_status or "UNVERIFIED", 0.5)


def compute_priority(eligibility: float, relevance: float, growth: float,
                     compensation: float, deadline: float, org: float,
                     weights: dict[str, float] | None = None) -> float:
    w = weights or DEFAULT_PRIORITY_WEIGHTS
    total = (
        w["eligibility"] * eligibility / 100
        + w["relevance"] * relevance / 100
        + w["growth"] * growth
        + w["compensation"] * compensation
        + w["deadline"] * deadline
        + w["org_quality"] * org
    )
    return round(total * 100.0, 1)


DEFAULT_PRIORITY_WEIGHTS: dict[str, float] = {
    "eligibility": 0.30, "relevance": 0.25, "growth": 0.15,
    "compensation": 0.10, "deadline": 0.10, "org_quality": 0.10,
}
