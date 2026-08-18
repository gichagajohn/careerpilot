"""Normalizer — converts raw listings into structured records.

Two paths (spec §20, §21):
  1. LLM path (preferred): specialized prompt → strict JSON → validated.
  2. No-LLM path (fallback): deterministic extraction from text, so the
     pipeline keeps working with zero API keys configured.

The LLM is given ONLY the listing text and is forbidden from inventing facts.
Jobs (Phase 2) and scholarships (Phase 3) share the RawListing format and
the fallback extractors.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from app.core.llm import get_provider
from app.schemas.opportunities import JobIn, ScholarshipIn
from app.services.prompts import build_message

logger = logging.getLogger("careerpilot.normalizer")


@dataclass
class RawListing:
    title: str
    url: str
    raw_text: str
    source_name: str
    source_type: str  # API / RSS / SEARCH / FETCH
    extra: dict = field(default_factory=dict)


@dataclass
class NormalizedJob:
    job: JobIn
    source_name: str
    source_type: str
    source_url: str


@dataclass
class NormalizedScholarship:
    scholarship: ScholarshipIn
    source_name: str
    source_type: str
    source_url: str


def normalize_listing(listing: RawListing, use_llm: bool = True) -> NormalizedJob | None:
    """Return a structured job or None if the listing has no usable title/text."""
    text = (listing.raw_text or "").strip()
    if not text and not listing.title:
        return None

    job: JobIn | None = None
    if use_llm:
        try:
            system, user = build_message(
                "job_extraction",
                source_name=listing.source_name,
                source_url=listing.url,
                raw_text=text[:12_000] or listing.title,
            )
            job = get_provider().complete_json(system, user, JobIn, task="job_extraction")
        except Exception as exc:  # any provider failure → deterministic fallback
            logger.warning("LLM extraction unavailable (%s); using deterministic path", exc)

    if job is None:
        job = extract_no_llm(listing)

    if not job.title:
        job.title = listing.title or "Untitled position"

    return NormalizedJob(
        job=job,
        source_name=listing.source_name,
        source_type=listing.source_type,
        source_url=listing.url,
    )


def normalize_scholarship_listing(
    listing: RawListing, use_llm: bool = True
) -> NormalizedScholarship | None:
    """Return a structured scholarship, with the funding-level evidence rule applied."""
    text = (listing.raw_text or "").strip()
    if not text and not listing.title:
        return None

    sch: ScholarshipIn | None = None
    if use_llm:
        try:
            system, user = build_message(
                "scholarship_extraction",
                source_name=listing.source_name,
                source_url=listing.url,
                raw_text=text[:14_000] or listing.title,
            )
            sch = get_provider().complete_json(system, user, ScholarshipIn, task="scholarship_extraction")
        except Exception as exc:
            logger.warning("LLM scholarship extraction unavailable (%s); deterministic path", exc)

    if sch is None:
        sch = extract_scholarship_no_llm(listing)

    # Spec §4: never mark "fully funded" unless the official source confirms it.
    sch.funding_level = assess_funding(text, sch.funding_level)

    if not sch.name:
        sch.name = listing.title or "Untitled scholarship"

    return NormalizedScholarship(
        scholarship=sch,
        source_name=listing.source_name,
        source_type=listing.source_type,
        source_url=listing.url,
    )


# ── Deterministic fallback extractor (no LLM) ──────────────────

_DEADLINE_PATTERNS = [
    re.compile(r"(20\d{2}-\d{2}-\d{2})"),
    re.compile(r"(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+20\d{2})", re.I),
    re.compile(r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+20\d{2})", re.I),
]

_REMOTE_WORDS = ("remote", "work from home", "work-from-home", "online")
_FULLTIME_WORDS = ("full-time", "full time")
_PARTTIME_WORDS = ("part-time", "part time")
_CONTRACT_WORDS = ("contract", "freelance")
_AI_WORDS = ("ai trainer", "ai evaluator", "ai data", "ai annotator", "ai tutor", "artificial intelligence trainer")
_LOCATIONS = {
    "kenya": "Kenya", "nairobi": "Nairobi, Kenya", "nigeria": "Nigeria", "ghana": "Ghana",
    "south africa": "South Africa", "uganda": "Uganda", "tanzania": "Tanzania",
    "ethiopia": "Ethiopia", "rwanda": "Rwanda", "egypt": "Egypt", "united kingdom": "United Kingdom",
    "uk": "United Kingdom", "united arab emirates": "UAE", "uae": "UAE", "qatar": "Qatar",
    "saudi arabia": "Saudi Arabia", "usa": "USA", "united states": "USA", "canada": "Canada",
    "germany": "Germany", "netherlands": "Netherlands", "singapore": "Singapore",
}
_CURRENCIES = {"kes": "KES", "ksh": "KES", "usd": "USD", "$": "USD", "eur": "EUR", "€": "EUR"}


def extract_no_llm(listing: RawListing) -> JobIn:
    text = listing.raw_text or listing.title or ""
    low = text.lower()

    title = listing.title
    if not title:
        for line in text.splitlines():
            line = line.strip()
            if 8 <= len(line) <= 150:
                title = line
                break

    organization: str | None = None
    for pattern in (r"company[:\s]+(.+)", r"organization[:\s]+(.+)", r"school[:\s]+(.+)"):
        m = re.search(pattern, text, re.I)
        if m:
            organization = m.group(1).strip().strip("|").strip()
            break

    location: str | None = None
    # prefer the most specific match ("Nairobi, Kenya" before "Kenya")
    for word, label in sorted(_LOCATIONS.items(), key=lambda kv: len(kv[0]), reverse=True):
        if re.search(rf"\b{re.escape(word)}\b", low):
            location = label
            break

    deadline: str | None = None
    for pattern in _DEADLINE_PATTERNS:
        m = pattern.search(text)
        if m:
            deadline = m.group(1)
            break

    salary_currency: str | None = None
    for word, code in _CURRENCIES.items():
        if re.search(rf"\b{re.escape(word)}\b", low):
            salary_currency = code
            break

    remote = any(w in low for w in _REMOTE_WORDS)
    is_ai = any(w in low for w in _AI_WORDS)

    employment_type: str | None = None
    if any(w in low for w in _FULLTIME_WORDS):
        employment_type = "Full-time"
    elif any(w in low for w in _PARTTIME_WORDS):
        employment_type = "Part-time"
    elif any(w in low for w in _CONTRACT_WORDS):
        employment_type = "Contract"

    requirements: list[str] = []
    preferred: list[str] = []
    mode = "none"  # "none" | "req" | "pref"
    for line in text.splitlines():
        s = line.strip().lstrip("-•*·")
        s = re.sub(r"^\d+[.)]\s*", "", s).strip()
        if not s:
            continue
        sl = s.lower().strip(":")
        if sl in ("requirements", "required qualifications", "qualifications"):
            mode = "req"
            continue
        if sl in ("preferred", "nice to have", "desired", "preferred qualifications"):
            mode = "pref"
            continue
        if len(s) < 8 or len(s) > 200:
            continue
        if mode == "req":
            requirements.append(s)
        elif mode == "pref":
            preferred.append(s)
        elif "requirement" in sl or "must have" in sl or "qualification" in sl or "essential" in sl:
            requirements.append(s)
        elif "preferred" in sl or "nice to have" in sl or "desirable" in sl:
            preferred.append(s)

    return JobIn(
        title=title,
        organization_name=organization,
        location=location,
        country=None if location and "," in (location or "") else location,
        employment_type=employment_type,
        salary_currency=salary_currency,
        description=text[:4000],
        requirements=requirements[:15],
        preferred_requirements=preferred[:10],
        deadline=deadline,
        application_url=listing.url,
        source_url=listing.url,
        remote=remote,
        is_ai_training=is_ai,
    )


def dump_raw(listing: RawListing) -> str:
    """Helper for debugging/search-run logs."""
    return json.dumps(
        {"title": listing.title, "url": listing.url, "source": listing.source_name},
        ensure_ascii=False,
    )


# ── Scholarship deterministic extractor (no LLM) ───────────────

_SCHOLARSHIP_FUNDING_STRONG = (
    "fully funded", "fully-funded", "fully financed", "fully-financed", "100% funded",
    "full funding", "complete funding", "fully paid",
)
_SCHOLARSHIP_FUNDING_TUITION_FREE = ("tuition-free", "tuition free", "no tuition", "free tuition")
_SCHOLARSHIP_FUNDING_TUITION = ("full tuition", "tuition covered", "tuition coverage")
_SCHOLARSHIP_ALLOWANCE = ("stipend", "living allowance", "monthly allowance", "maintenance grant", "monthly grant")
_SCHOLARSHIP_ACCOMMODATION = ("accommodation", "housing", "room and board", "board and lodging", "dormitory")


def assess_funding(text: str, current: str | None = None) -> str:
    """Evidence-based funding classification (spec §4: never claim FULLY FUNDED
    without explicit confirmation)."""
    low = (text or "").lower()

    def has(*phrases: str) -> bool:
        return any(p in low for p in phrases)

    strong = has(*_SCHOLARSHIP_FUNDING_STRONG)
    tuition_free = has(*_SCHOLARSHIP_FUNDING_TUITION_FREE)
    full_tuition = has(*_SCHOLARSHIP_FUNDING_TUITION)
    allowance = has(*_SCHOLARSHIP_ALLOWANCE)
    accommodation = has(*_SCHOLARSHIP_ACCOMMODATION)

    if strong or (full_tuition and allowance and accommodation):
        return "FULLY FUNDED"
    if tuition_free or full_tuition:
        return "TUITION-FREE" if tuition_free else "TUITION-ONLY"
    if current in ("FULLY FUNDED", "TUITION-FREE", "TUITION-ONLY", "PARTIAL"):
        # LLM saw something but the text evidence is weaker — stay conservative
        return "PARTIAL" if has("partial") else "UNSPECIFIED"
    if has("partial"):
        return "PARTIAL"
    return "UNSPECIFIED"


def extract_scholarship_no_llm(listing: RawListing) -> ScholarshipIn:
    text = listing.raw_text or listing.title or ""
    low = text.lower()

    university: str | None = None
    for pattern in (r"university[:\s]+([^\n|,]+)", r"at ([A-Z][A-Za-z .'&-]+ [Uu]niversity)"):
        m = re.search(pattern, text)
        if m:
            university = m.group(1).strip()
            break

    country: str | None = None
    for word, label in sorted(_LOCATIONS.items(), key=lambda kv: len(kv[0]), reverse=True):
        if re.search(rf"\b{re.escape(word)}\b", low):
            country = label
            break

    deadline: str | None = None
    for pattern in _DEADLINE_PATTERNS:
        m = pattern.search(text)
        if m:
            deadline = m.group(1)
            break

    degree_level = "Master's" if re.search(r"\bmaster'?s?\b", low) else (
        "PhD" if re.search(r"\bph\.?d\b", low) else None)

    def find_field(*patterns: str) -> str | None:
        for pat in patterns:
            m = re.search(pat, text, re.I)
            if m:
                return m.group(0).strip()[:200]
        return None

    required_classification = find_field(
        r"first class honours", r"upper second[ -]?class", r"\b2:1\b", r"\b2\.1\b",
        r"second class upper", r"gpa of [\d.]+",
    )
    english_requirement = find_field(r"ielts [\d.]+\+?", r"toefl [\d]+", r"english (?:proficiency|requirement)")
    age_requirement = find_field(r"(?:under|below|age)[ :]?\d{2,3}", r"(?:aged?\s)?\d{2,3}\s*(?:years)?")

    return ScholarshipIn(
        name=listing.title or "Untitled scholarship",
        university=university,
        country=country,
        programme=None,
        degree_level=degree_level,
        funding_level=assess_funding(text, None),
        tuition_coverage="Yes" if any(p in low for p in _SCHOLARSHIP_FUNDING_TUITION + _SCHOLARSHIP_FUNDING_TUITION_FREE) else None,
        accommodation="Yes" if any(p in low for p in _SCHOLARSHIP_ACCOMMODATION) else None,
        living_allowance="Yes" if any(p in low for p in _SCHOLARSHIP_ALLOWANCE) else None,
        travel_allowance="Yes" if "travel" in low and "allowance" in low else None,
        insurance="Yes" if "insurance" in low else None,
        application_fee=None,
        eligibility=text[:500] or None,
        required_classification=required_classification,
        required_field=None,
        work_experience_required=None,
        english_requirement=english_requirement,
        age_requirement=age_requirement,
        deadline=deadline,
        application_url=listing.url,
        official_url=listing.extra.get("feed_url") or listing.url,
        open_to_kenyans="kenyan" in low or "kenya" in low,
        open_to_africans="african" in low or "africa" in low,
    )
