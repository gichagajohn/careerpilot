"""Duplicate detection — one opportunity, many sources (spec §24).

Strategy:
  1. Exact normalized key (title + organization + country) → same cluster.
  2. Fuzzy fallback: Jaccard similarity over title/org tokens with a strong
     description-overlap bonus. Above threshold → same cluster.

The canonical record keeps all metadata; every other listing becomes a row in
job_sources so the original source URLs are never lost.
"""
from __future__ import annotations

import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Job, JobSource, Scholarship, ScholarshipSource

SIMILARITY_THRESHOLD = 0.72


def normalize_key(title: str, organization: str | None, country: str | None) -> str:
    parts = [title or "", organization or "", country or ""]
    joined = " ".join(parts).lower()
    return re.sub(r"[^a-z0-9]+", " ", joined).strip()


def token_set(text: str | None, limit: int = 200) -> set[str]:
    if not text:
        return set()
    return set(re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())[:limit].split())


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _candidate_similarity(candidate_title: str, candidate_org: str | None,
                          candidate_country: str | None, job: Job) -> float:
    # Same title but two named, different employers → distinct opportunities
    if (candidate_org and job.organization_name
            and candidate_org.lower() != job.organization_name.lower()):
        return 0.0
    title_sim = jaccard(token_set(candidate_title), token_set(job.title))
    if title_sim >= 0.999:
        # identical titles (and no conflicting employer) → same posting
        return 0.9
    org_bonus = 1.0 if (candidate_org and job.organization_name
                        and candidate_org.lower() == job.organization_name.lower()) else 0.0
    country_bonus = 1.0 if (candidate_country and job.country
                            and candidate_country.lower() == job.country.lower()) else 0.0
    return title_sim * 0.7 + org_bonus * 0.2 + country_bonus * 0.1


def find_duplicate(db: Session, title: str, organization: str | None,
                   country: str | None) -> Job | None:
    """Return the canonical Job this listing duplicates, or None."""
    key = normalize_key(title, organization, country)
    if len(key.split()) >= 3:
        # exact normalized-key match (case/punctuation-insensitive)
        exact = db.scalar(
            select(Job).where(
                Job.is_canonical.is_(True),
                func.lower(func.replace(Job.title, "  ", " ")).in_([title.lower()]),
                Job.organization_name.ilike((organization or "%") if organization else "%"),
                Job.country == country,
            ).limit(1)
        )
        if exact:
            return exact

    # fuzzy: compare against recent canonical jobs (bounded scan, personal scale)
    recent = db.scalars(
        select(Job)
        .where(Job.is_canonical.is_(True))
        .order_by(Job.discovery_date.desc())
        .limit(800)
    ).all()
    best: Job | None = None
    best_score = 0.0
    for job in recent:
        score = _candidate_similarity(title, organization, country, job)
        if score > best_score:
            best_score = score
            best = job
    return best if best_score >= SIMILARITY_THRESHOLD else None


def new_cluster_id() -> str:
    return uuid.uuid4().hex[:16]


def attach_source(db: Session, job: Job, source_name: str, source_type: str,
                  source_url: str | None) -> bool:
    """Record another listing source for a job; returns True if newly added."""
    if source_url:
        exists = db.scalar(
            select(JobSource.id).where(
                JobSource.job_id == job.id, JobSource.source_url == source_url
            )
        )
        if exists:
            return False
    db.add(
        JobSource(
            job_id=job.id,
            source_type=source_type,
            source_name=source_name,
            source_url=source_url,
        )
    )
    db.flush()  # visible to subsequent queries in this session
    return True


# ── Scholarships (Phase 3) ─────────────────────────────────────


def find_duplicate_scholarship(db: Session, name: str, university: str | None) -> Scholarship | None:
    """Return the canonical Scholarship this listing duplicates, or None."""
    exact = db.scalar(
        select(Scholarship).where(
            Scholarship.is_canonical.is_(True),
            func.lower(Scholarship.name) == name.lower(),
            Scholarship.university.ilike((university or "%") if university else "%"),
        ).limit(1)
    )
    if exact:
        return exact

    recent = db.scalars(
        select(Scholarship)
        .where(Scholarship.is_canonical.is_(True))
        .order_by(Scholarship.discovery_date.desc())
        .limit(800)
    ).all()
    best: Scholarship | None = None
    best_score = 0.0
    for sch in recent:
        name_sim = jaccard(token_set(name), token_set(sch.name))
        uni_bonus = 1.0 if (university and sch.university
                            and university.lower() == sch.university.lower()) else 0.0
        score = name_sim * 0.8 + uni_bonus * 0.2
        if score > best_score:
            best_score = score
            best = sch
    return best if best_score >= SIMILARITY_THRESHOLD else None


def attach_scholarship_source(db: Session, scholarship: Scholarship, source_name: str,
                              source_type: str, source_url: str | None) -> bool:
    if source_url:
        exists = db.scalar(
            select(ScholarshipSource.id).where(
                ScholarshipSource.scholarship_id == scholarship.id,
                ScholarshipSource.source_url == source_url,
            )
        )
        if exists:
            return False
    db.add(
        ScholarshipSource(
            scholarship_id=scholarship.id,
            source_type=source_type,
            source_name=source_name,
            source_url=source_url,
        )
    )
    db.flush()
    return True
