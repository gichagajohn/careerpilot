"""Agent 3 — Opportunity Verifier: 10 deterministic checks (spec §5).

Each opportunity (job or scholarship) is evaluated against a checklist.
Results stored in verification_results + written to the opportunity's
verification_status and verification_notes.
"""
from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import urlparse

import httpx
from dateutil import parser as dtparser
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job, Scholarship, VerificationResult

logger = logging.getLogger("careerpilot.verifier")

USER_AGENT = "CareerPilotAI/0.2 (personal career assistant; contact: johngichaga8@gmail.com)"

KNOWN_REPUTABLE_DOMAINS = [
    "adzuna.co.ke", "adzuna.com", "remotive.com", "remoteok.io", "remoteok.com",
    "arbeitnow.com", "reliefweb.int", "un.org", "unesco.org", "unicef.org",
    "chevening.org", "daad.de", "eacea.ec.europa.eu", "cscuk.fcdo.gov.uk",
    "mastercardfdn.org", "nexteinstein.org", "mandelarhodes.org",
    "fulbrightonline.org", "gatescambridge.org",
    "opportunitiesforyouth.org", "afterschoolafrica.com",
    "google.com", "serper.dev", "tavily.com",
]

SUSPICIOUS_PAYMENT_KEYWORDS = [
    "registration fee", "processing fee", "visa fee",
    "bank transfer", "crypto", "bitcoin", "wire transfer",
    "western union", "moneygram", "handling charge",
    "refundable deposit",
]


class CheckResult:
    __slots__ = ("name", "passed", "details")

    def __init__(self, name: str, passed: bool, details: str = "") -> None:
        self.name = name
        self.passed = passed
        self.details = details


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _record(db: Session, entity_type: str, entity_id: int, check: CheckResult) -> None:
    db.add(
        VerificationResult(
            entity_type=entity_type,
            entity_id=entity_id,
            check_name=check.name,
            passed=check.passed,
            details=check.details[:500],
            result="PASS" if check.passed else "FAIL",
            checked_at=_now_iso(),
        )
    )


def _parse_deadline(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return dtparser.parse(text, fuzzy=True)
    except (dtparser.ParserError, ValueError):
        return None


def _domain(url: str | None) -> str | None:
    if not url or not url.startswith("http"):
        return None
    return urlparse(url).netloc.lower()


def _levenshtein(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(curr[-1] + 1, prev[j + 1] + 1, prev[j] + (c1 != c2)))
        prev = curr
    return prev[-1]


def _typosquat_score(domain: str | None) -> int:
    """Return minimum Levenshtein distance to any known reputable domain.
    0 = exact match, low = likely legitimate, high = safe or unknown."""
    if not domain:
        return 0
    best = 99
    for known in KNOWN_REPUTABLE_DOMAINS:
        if domain == known or domain.endswith("." + known):
            return 0
        d = _levenshtein(domain, known)
        if d < best:
            best = d
    return best


# ── Individual checks ──────────────────────────────────────────


def check_org_exists(org_name: str | None) -> CheckResult:
    if not org_name or len(org_name.strip()) < 3:
        return CheckResult("org_exists", True, "Org name too short to verify")
    if org_name.startswith("("):
        return CheckResult("org_exists", True, "Parenthetical, skipped")
    # Try polite HTTPS GET on candidate domains
    query = org_name.strip().lower().replace(" ", "")
    candidates = [
        f"https://www.{query}.com",
        f"https://{query}.org",
        f"https://{query}.ac.ke",
    ]
    for url in candidates:
        try:
            resp = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=8)
            if resp.status_code < 400:
                return CheckResult("org_exists", True, f"Accessible at {urlparse(url).netloc}")
        except httpx.HTTPError:
            continue
    return CheckResult("org_exists", False, f"Could not confirm domain for: {org_name}")


def check_source_reputable(source_name: str, source_url: str | None) -> CheckResult:
    if source_name in ("websearch", "rss") or source_name.startswith("page:"):
        return CheckResult("source_reputable", True, f"Trusted type: {source_name}")
    domain = _domain(source_url)
    if domain and (_typosquat_score(domain) == 0):
        return CheckResult("source_reputable", True, f"Recognised domain: {domain}")
    return CheckResult("source_reputable", False, f"Unknown or unreputable source: {source_name}")


def check_url_legitimate(url: str | None) -> CheckResult:
    if not url:
        return CheckResult("url_legitimate", False, "No URL provided")
    if not url.startswith("http"):
        return CheckResult("url_legitimate", False, "Not an HTTP(S) URL")
    if not url.startswith("https://"):
        return CheckResult("url_legitimate", False, "Not HTTPS")
    domain = _domain(url)
    if domain is None:
        return CheckResult("url_legitimate", False, "Invalid domain")
    ts = _typosquat_score(domain)
    if ts <= 2 and ts > 0:
        return CheckResult("url_legitimate", False,
                           f"Domain {domain} is a close variation of a known domain (Levenshtein={ts})")
    return CheckResult("url_legitimate", True, "HTTPS domain appears legitimate")


def check_deadline_valid(deadline: str | None) -> CheckResult:
    dt = _parse_deadline(deadline)
    if dt is None:
        return CheckResult("deadline_valid", False, "Unparseable deadline — cannot confirm validity")
    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
    if dt < now:
        return CheckResult("deadline_valid", False, f"Expired: {deadline}")
    return CheckResult("deadline_valid", True, f"Still valid: {deadline}")


def check_duplicate_group(duplicate_group: str | None) -> CheckResult:
    if duplicate_group:
        return CheckResult("duplicate_group", True, f"Part of cluster {duplicate_group[:12]}")
    return CheckResult("duplicate_group", False, "Singleton — not deduplicated")


def check_payment_requirements(text: str | None, entity_type: str = "job") -> CheckResult:
    """Payment keyword scan. For scholarships, application fees may be legitimate."""
    if entity_type == "scholarship":
        return CheckResult("payment_requirements", True, "Scholarship — fee may be legitimate")
    if not text:
        return CheckResult("payment_requirements", True, "No text to scan")
    low = text.lower()
    found = [kw for kw in SUSPICIOUS_PAYMENT_KEYWORDS if kw in low]
    if found:
        return CheckResult(
            "payment_requirements", False,
            f"Suspicious payment keywords: {', '.join(found)}",
        )
    return CheckResult("payment_requirements", True, "No suspicious payment keywords")


def check_job_exists(source_url: str | None, description: str | None) -> CheckResult:
    if not source_url or not source_url.startswith("http"):
        return CheckResult("job_exists", False, "No verifiable listing URL")
    if not description or len(description) < 80:
        return CheckResult("job_exists", False, "Description too short to confirm")
    try:
        resp = httpx.get(source_url, headers={"User-Agent": USER_AGENT}, timeout=10,
                          follow_redirects=True)
        if resp.status_code == 200:
            return CheckResult("job_exists", True, "Listing page reachable")
        elif resp.status_code in (404, 410):
            return CheckResult("job_exists", False, f"Listing returned HTTP {resp.status_code}")
    except httpx.HTTPError:
        pass
    return CheckResult("job_exists", False, "Could not fetch listing page")


def check_scholarship_exists(official_url: str | None, name: str | None) -> CheckResult:
    if not official_url or not official_url.startswith("http"):
        return CheckResult("scholarship_exists", False, "No official URL to verify")
    if not name or "untitled" in name.lower():
        return CheckResult("scholarship_exists", False, "Name too generic to confirm")
    try:
        resp = httpx.get(official_url, headers={"User-Agent": USER_AGENT}, timeout=10,
                          follow_redirects=True)
        if resp.status_code == 200:
            return CheckResult("scholarship_exists", True, "Official page reachable")
    except httpx.HTTPError:
        pass
    return CheckResult("scholarship_exists", False, "Could not fetch official page")


def check_process_consistent(app_url: str | None, official_url: str | None) -> CheckResult:
    app_domain = _domain(app_url)
    off_domain = _domain(official_url)
    if not app_domain:
        return CheckResult("process_consistent", False, "No application URL")
    if "gmail" in app_domain or "outlook" in app_domain:
        return CheckResult("process_consistent", False, f"Personal email domain: {app_domain}")
    if off_domain and app_domain != off_domain and not app_domain.endswith("." + off_domain):
        return CheckResult("process_consistent", False,
                            f"Application domain {app_domain} differs from official {off_domain}")
    return CheckResult("process_consistent", True, "Application on official domain")


def check_programme_exists(
    programme: str | None, university: str | None, official_url: str | None
) -> CheckResult:
    if not programme or not university:
        return CheckResult("programme_exists", False, "Missing programme or university")
    if official_url and official_url.startswith("http"):
        try:
            resp = httpx.get(official_url, headers={"User-Agent": USER_AGENT},
                              timeout=10, follow_redirects=True)
            if resp.status_code == 200 and programme.lower() in resp.text[:10000].lower():
                return CheckResult("programme_exists", True, "Programme mentioned on official page")
        except httpx.HTTPError:
            pass
    return CheckResult("programme_exists", False, "Could not confirm programme on university site")


# ── Orchestration ──────────────────────────────────────────────


def _compute_status(entity, check_results: dict[str, CheckResult]) -> None:
    dr = check_results.get("deadline_valid")
    if dr and not dr.passed and "Expired" in (dr.details or ""):
        entity.verification_status = "EXPIRED"
        entity.verification_notes = dr.details
        return

    suspicious_names = {"payment_requirements", "process_consistent"}
    any_suspicious = any(
        not r.passed for n, r in check_results.items() if n in suspicious_names
    )
    if any_suspicious:
        entity.verification_status = "SUSPICIOUS"
        entity.verification_notes = "; ".join(
            r.details for r in check_results.values() if not r.passed
        )
        return

    all_pass = all(r.passed for r in check_results.values())
    if all_pass:
        entity.verification_status = "VERIFIED"
        entity.verification_notes = "All checks passed"
    else:
        fails = [f"{n}: {r.details}" for n, r in check_results.items() if not r.passed]
        pas = [n for n, r in check_results.items() if r.passed]
        # Most checks passed but some failed → Likely Verified
        if len(pas) > len(fails):
            entity.verification_status = "LIKELY VERIFIED"
        else:
            entity.verification_status = "UNVERIFIED"
        entity.verification_notes = "; ".join(fails)[:500]


def verify_job(db: Session, job: Job) -> None:
    checks = {
        "org_exists": check_org_exists(job.organization_name),
        "source_reputable": check_source_reputable(
            (job.sources[0].source_name if job.sources else "unknown"),
            job.source_url,
        ),
        "url_legitimate": check_url_legitimate(job.application_url),
        "deadline_valid": check_deadline_valid(job.deadline),
        "duplicate_group": check_duplicate_group(job.duplicate_group),
        "job_exists": check_job_exists(job.source_url, job.description),
        "payment_requirements": check_payment_requirements(job.description, "job"),
        "process_consistent": check_process_consistent(job.application_url, job.source_url),
    }
    for result in checks.values():
        _record(db, "job", job.id, result)
    _compute_status(job, checks)
    db.commit()


def verify_scholarship(db: Session, sch: Scholarship) -> None:
    checks = {
        "org_exists": check_org_exists(sch.university),
        "source_reputable": check_source_reputable(
            (sch.sources[0].source_name if sch.sources else "unknown"),
            sch.official_url,
        ),
        "url_legitimate": check_url_legitimate(sch.official_url),
        "deadline_valid": check_deadline_valid(sch.deadline),
        "duplicate_group": check_duplicate_group(sch.duplicate_group),
        "scholarship_exists": check_scholarship_exists(sch.official_url, sch.name),
        "programme_exists": check_programme_exists(sch.programme, sch.university, sch.official_url),
        "process_consistent": check_process_consistent(sch.application_url, sch.official_url),
        "payment_requirements": check_payment_requirements(None, "scholarship"),
    }
    for result in checks.values():
        _record(db, "scholarship", sch.id, result)
    _compute_status(sch, checks)
    db.commit()


def run_verification_pass(
    db: Session, entity_type: str | None = None
) -> dict:
    stats = {"jobs_verified": 0, "scholarships_verified": 0, "expired": 0, "suspicious": 0, "errors": []}

    if entity_type in (None, "job"):
        jobs = db.scalars(
            select(Job)
            .where(Job.is_canonical.is_(True), Job.verification_status == "UNVERIFIED")
            .limit(100)
        ).all()
        for job in jobs:
            try:
                verify_job(db, job)
                stats["jobs_verified"] += 1
                if job.verification_status == "EXPIRED":
                    stats["expired"] += 1
                elif job.verification_status == "SUSPICIOUS":
                    stats["suspicious"] += 1
            except Exception as exc:
                stats["errors"].append(f"job {job.id}: {exc}")
                logger.exception("Verification failed for job %d", job.id)

    if entity_type in (None, "scholarship"):
        scholarships = db.scalars(
            select(Scholarship).where(Scholarship.verification_status == "UNVERIFIED").limit(100)
        ).all()
        for sch in scholarships:
            try:
                verify_scholarship(db, sch)
                stats["scholarships_verified"] += 1
                if sch.verification_status == "EXPIRED":
                    stats["expired"] += 1
                elif sch.verification_status == "SUSPICIOUS":
                    stats["suspicious"] += 1
            except Exception as exc:
                stats["errors"].append(f"scholarship {sch.id}: {exc}")
                logger.exception("Verification failed for scholarship %d", sch.id)

    db.commit()
    return stats