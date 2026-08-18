"""Relevance pre-filter for discovered listings.

Phase 2 keeps discovery broad but skips obvious out-of-scope roles
(sales, marketing, design, generic software engineering) so the opportunity
pool stays clean until Phase 5 does full matching/ranking.

Rules:
  - TITLE_PATTERNS: a strong in-scope signal in the title keeps the listing.
  - TEXT_PATTERNS: strong signals in the first ~3,000 chars of text also keep it.
  - Generic tech skills (Python, JavaScript...) are deliberately NOT enough —
    otherwise every software job would match John's CS-teaching skill set.
Disable with JOBS_RELEVANCE_FILTER=false.
"""
from __future__ import annotations

import re

from .normalizer import RawListing

TITLE_PATTERNS = [
    r"\bteach\w*\b",
    r"\beducat\w*\b",
    r"\bmath\w*\b",
    r"\bcurriculum\b",
    r"\binstructional\b",
    r"\binstructor\b",
    r"\btutor\w*\b",
    r"\bstem\b",
    r"\bedtech\b",
    r"\bict\b",
    r"\bcomputer science\b",
    r"\bcomputer studies\b",
    r"\bprogramming\b",
    r"\bcoding\b",
    r"\bschool\b",
    r"\buniversity\b",
    r"\bcollege\b",
    r"\blecturer\b",
    r"\bprofessor\b",
    r"\bai\s+(train|evaluat|tutor|data|math|content)\w*\b",
    r"\bdata label\w*\b",
    r"\bdata annotat\w*\b",
    r"\breviewer\b",
    r"\bassess\w*\b",
    r"\bpedagogy\b",
]

TEXT_PATTERNS = [
    r"\bteach(er|ing|es)?\b",
    r"\beducat\w*\b",
    r"\bmath\w*\b",
    r"\bcurriculum\b",
    r"\binstructional\b",
    r"\btutor(ing)?\b",
    r"\bstem\b",
    r"\bedtech\b",
    r"\beducational technology\b",
    r"\bict\b",
    r"\bcomputer science\b",
    r"\bcomputer studies\b",
    r"\bcoding\b",
    r"\bprogramming\b",
    r"\bai train(er|ing)?\b",
    r"\bai evaluat\w*\b",
    r"\bai data\b",
    r"\bai tutor\b",
    r"\bdata label\w*\b",
    r"\bdata annotat\w*\b",
    r"\bcontent reviewer\b",
    r"\bassessment\b",
    r"\bpedagogy\b",
    r"\bschool\b",
    r"\buniversity\b",
    r"\bcollege\b",
    r"\blecturer\b",
    r"\bprofessor\b",
]

_title_re = [re.compile(p, re.IGNORECASE) for p in TITLE_PATTERNS]
_text_re = [re.compile(p, re.IGNORECASE) for p in TEXT_PATTERNS]


def is_relevant(listing: RawListing) -> bool:
    """True if the listing shows any in-scope signal (conservative gate)."""
    title = listing.title or ""
    if any(p.search(title) for p in _title_re):
        return True
    text = (listing.raw_text or "")[:3000]
    return any(p.search(text) for p in _text_re)


# ── Scholarship relevance (Phase 3) ─────────────────────────────
# Generous: scholarships, fellowships, grants, funded Master's, stipends,
# tuition coverage, open-call academic funding.
_SCHOLARSHIP_TITLE_PATTERNS = [
    r"\bscholarship\w*\b",
    r"\bfellowship\w*\b",
    r"\bgrant\w*\b",
    r"\bmaster'?s\b",
    r"\btuition\w*\b",
    r"\bfully funded\b",
    r"\bstipend\b",
    r"\bdegree\b",
    r"\bpostgraduate\b",
    r"\bgraduate (?:scholarship|programme|program)\b",
]

_SCHOLARSHIP_TEXT_PATTERNS = [
    r"\bscholarship\w*\b",
    r"\bfellowship\w*\b",
    r"\bgrant\w*\b",
    r"\bmaster'?s\b",
    r"\btuition\w*\b",
    r"\bfully funded\b",
    r"\bstipend\b",
    r"\bpostgraduate\b",
    r"\bapplication (?:deadline|fee)\b",
]

_sch_title_re = [re.compile(p, re.IGNORECASE) for p in _SCHOLARSHIP_TITLE_PATTERNS]
_sch_text_re = [re.compile(p, re.IGNORECASE) for p in _SCHOLARSHIP_TEXT_PATTERNS]


def is_relevant_scholarship(listing: RawListing) -> bool:
    title = listing.title or ""
    if any(p.search(title) for p in _sch_title_re):
        return True
    text = (listing.raw_text or "")[:3000]
    return any(p.search(text) for p in _sch_text_re)
