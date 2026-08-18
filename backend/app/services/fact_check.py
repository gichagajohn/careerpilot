"""FactCheck gate — the anti-fabrication core (spec §22).

Every claim in a generated document must trace to the master profile.
Pipeline:
  1. Assemble a FactStore from the master profile (the single source of truth).
  2. For each content line, extract candidate named-entities (organisations,
     institutions, degrees, classifications, skills, locations) and verify each
     against the store with normalized containment.
  3. Run static fabrication detectors (curriculum claims, awards, references,
     salary history, invented years, international experience).
  4. UNVERIFIED or PROHIBITED lines are REMOVED from the final document and
     listed in the report as CLAIM / SOURCE / VERIFIED: NO.

The CV generator is deterministic and pulls only from the profile, so the gate
is a safety net — especially for any LLM-authored summary text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models import MasterProfile

# ── static fabrication detectors (spec §22 list) ───────────────
PROHIBITED_PATTERNS = [
    (r"\binternational (school|curriculum) (experience|teaching|background)\b", "invented international experience"),
    (r"\b(igcse|international baccalaureate|a-level|o-level|cambridge)[^.\n]{0,40}(experience|taught|teaching|curriculum)", "unclaimed curriculum experience"),
    (r"\baward\w*[^.\n]{0,30}(won|received|achieved|recipient)\b", "invented award"),
    (r"\breferences?[:\s]|available upon request", "reference section"),
    (r"\bsalary (history|expectation)\b", "salary history"),
    (r"\b(?:gpa|grade)[:\s]?[a-d][+-]?|aggregate[:\s]?\d+", "unverified grade"),
    (r"\b(fluent|native)\b.*(english|kiswahili|swahili)", "unclaimed language fluency"),
]

# Contact/identity lines that come straight from the profile
_LABEL_PREFIXES = ("phone:", "email:", "location:", "nationality:", "name:",
                   "subjects:", "grades:", "classes:", "grades/classes:")

_STRUCTURAL_WORDS = {
    "skills", "education", "experience", "summary", "contact", "certifications",
    "registration", "professional", "teaching", "teacher", "the", "and", "with",
    "from", "for", "at", "in", "of", "on", "a", "an", "as", "to", "current",
    "strong", "currently", "having", "including", "years", "year", "classes",
    "subjects", "grades", "phone", "email", "location", "nationality", "name",
}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


@dataclass
class FactStore:
    organizations: set[str] = field(default_factory=set)
    institutions: set[str] = field(default_factory=set)
    degrees: set[str] = field(default_factory=set)
    fields: set[str] = field(default_factory=set)
    skills: set[str] = field(default_factory=set)
    certifications: set[str] = field(default_factory=set)
    subjects: set[str] = field(default_factory=set)
    grades: set[str] = field(default_factory=set)
    registration: set[str] = field(default_factory=set)
    classifications: set[str] = field(default_factory=set)
    names: set[str] = field(default_factory=set)
    locations: set[str] = field(default_factory=set)
    roles: set[str] = field(default_factory=set)

    def all_terms(self) -> set[str]:
        terms: set[str] = set()
        for bucket in (self.organizations, self.institutions, self.degrees, self.fields,
                       self.skills, self.certifications, self.subjects, self.grades,
                       self.registration, self.classifications, self.names, self.locations,
                       self.roles):
            terms |= {_norm(t) for t in bucket}
        return terms


def build_fact_store(profile: MasterProfile) -> FactStore:
    store = FactStore()
    for exp in profile.experience:
        if exp.organization:
            store.organizations.add(_norm(exp.organization))
        if exp.role:
            store.roles.add(_norm(exp.role))
        store.subjects.update(_norm(s) for s in (exp.subjects or []))
        store.grades.update(_norm(g) for g in (exp.grades or []))
    for edu in profile.education:
        if edu.institution:
            store.institutions.add(_norm(edu.institution))
        if edu.degree:
            store.degrees.add(_norm(edu.degree))
        if edu.field:
            store.fields.add(_norm(edu.field))
        if edu.classification:
            store.classifications.add(_norm(edu.classification))
    for skill in profile.skills:
        if skill.approved:
            store.skills.add(_norm(skill.name))
    for cert in profile.certifications:
        if cert.name:
            store.certifications.add(_norm(cert.name))
    reg = (profile.professional_registration or "").strip()
    if reg:
        store.registration.add(_norm(reg))
        store.registration.update(_norm(t) for t in reg.split() if len(t) > 3)
    if profile.full_name:
        store.names.add(_norm(profile.full_name))
        store.names.update(_norm(t) for t in profile.full_name.split())
    for loc in [profile.location, profile.nationality, profile.profession]:
        if loc:
            store.locations.add(_norm(loc))
            store.locations.update(_norm(t) for t in loc.split() if len(t) > 3)
    from app.services.scoring import profile_years_experience
    store.years_experience = profile_years_experience(profile)
    return store


def _extract_candidates(line: str) -> list[str]:
    cands: list[str] = []
    # capitalized multi-word sequences → organisations, institutions, degrees...
    for m in re.finditer(r"\b([A-Z][A-Za-z&.'-]+(?:\s+[A-Z][A-Za-z&.'-]+){0,3})\b", line):
        cands.append(m.group(1))
    # standalone tokens listed after a "Skills:" label
    m = re.search(r"(?i)\bskills?\s*[:]\s*(.+)$", line)
    if m:
        cands += re.findall(r"[A-Za-z][A-Za-z0-9+.#-]{2,}", m.group(1))
    out: list[str] = []
    for c in cands:
        n = _norm(c)
        if n and n not in _STRUCTURAL_WORDS and n not in out:
            out.append(c)
    return out


def _in_store(candidate: str, store: FactStore) -> bool:
    c = _norm(candidate)
    if len(c) < 3:
        return True  # tiny tokens are not meaningful claims
    for term in store.all_terms():
        if len(term) >= 3 and (c in term or term in c):
            return True
    return False


@dataclass
class ClaimResult:
    claim: str
    source: str
    verified: bool

    def as_dict(self) -> dict:
        return {"claim": self.claim, "source": self.source, "verified": self.verified}


@dataclass
class FactCheckReport:
    total_claims: int
    verified_claims: int
    removed_claims: int
    prohibited_findings: list[str] = field(default_factory=list)
    report: list[ClaimResult] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "total_claims": self.total_claims,
            "verified_claims": self.verified_claims,
            "removed_claims": self.removed_claims,
            "prohibited_findings": self.prohibited_findings,
            "report": [r.as_dict() for r in self.report],
        }


def verify_line(line: str, store: FactStore) -> ClaimResult:
    stripped = line.strip()
    low = stripped.lower()
    if any(low.startswith(p) for p in _LABEL_PREFIXES):
        return ClaimResult(stripped, "profile_field", True)  # identity data from the profile
    # years-of-experience claims must match the profile's computed years
    years_match = re.search(r"\b(\d+(?:\.\d+)?)\s+years?\b", low)
    if years_match and float(years_match.group(1)) > store.years_experience + 0.5:
        return ClaimResult(stripped, "invented_years", False)
    candidates = _extract_candidates(stripped)
    if not candidates:
        return ClaimResult(stripped, "structural", True)
    missing = [c for c in candidates if not _in_store(c, store)]
    if missing:
        return ClaimResult(stripped, "master_profile", False)
    return ClaimResult(stripped, "master_profile", True)


def _detect_prohibited(text: str) -> list[str]:
    findings: list[str] = []
    for pattern, label in PROHIBITED_PATTERNS:
        if re.search(pattern, text, re.I):
            findings.append(label)
    return findings


def fact_check_document(lines: list[str], profile: MasterProfile) -> tuple[FactCheckReport, list[str]]:
    """Verify every content line; returns (report, kept_lines)."""
    store = build_fact_store(profile)
    report = FactCheckReport(total_claims=0, verified_claims=0, removed_claims=0)

    kept: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        report.total_claims += 1
        result = verify_line(stripped, store)
        report.report.append(result)
        if result.verified:
            kept.append(stripped)
            report.verified_claims += 1
        else:
            report.removed_claims += 1

    # hard rule: scan the ORIGINAL content — any prohibited fabrication
    # (invented international experience, awards, references, salary history,
    # unclaimed curriculum) voids the entire document, not just that line.
    report.prohibited_findings = _detect_prohibited("\n".join(lines))
    if report.prohibited_findings:
        return report, []
    return report, kept
