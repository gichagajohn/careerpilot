"""Deduplication tests (spec §24 — one opportunity, many sources)."""
from __future__ import annotations

from app.models import Job, JobSource
from app.services.dedup import attach_source, find_duplicate, new_cluster_id, normalize_key


def _job(db, title, org, country="Kenya"):
    job = Job(
        title=title,
        organization_name=org,
        country=country,
        description=f"Full description for {title} at {org} teaching mathematics and computer studies.",
        status="DISCOVERED",
        verification_status="UNVERIFIED",
        duplicate_group=new_cluster_id(),
    )
    db.add(job)
    db.flush()
    return job


def test_exact_duplicate_found(db_session):
    job = _job(db_session, "Mathematics Teacher", "Nova Pioneer")
    dup = find_duplicate(db_session, "Mathematics Teacher", "Nova Pioneer", "Kenya")
    assert dup is not None and dup.id == job.id


def test_normalized_key_ignores_case_punctuation():
    assert normalize_key("Mathematics Teacher!", "Nova  Pioneer", "Kenya") == normalize_key(
        "mathematics teacher", "Nova Pioneer", "Kenya"
    )


def test_fuzzy_duplicate_found(db_session):
    job = _job(db_session, "Mathematics Teacher", "Nova Pioneer")
    dup = find_duplicate(db_session, "Mathematics Teacher - Nairobi", "Nova Pioneer", "Kenya")
    assert dup is not None and dup.id == job.id


def test_distinct_job_not_flagged(db_session):
    _job(db_session, "Mathematics Teacher", "Nova Pioneer")
    dup = find_duplicate(db_session, "ICT Technician", "Different Company", "Uganda")
    assert dup is None


def test_attach_source_and_dedup(db_session):
    job = _job(db_session, "Computer Studies Teacher", "School A")

    added = attach_source(db_session, job, "adzuna", "API", "https://adzuna.co.ke/x")
    assert added is True

    # same URL again → not added
    added = attach_source(db_session, job, "adzuna", "API", "https://adzuna.co.ke/x")
    assert added is False

    # different URL → added (one job, multiple sources)
    added = attach_source(db_session, job, "websearch", "SEARCH", "https://school.example/jobs")
    assert added is True

    sources = db_session.query(JobSource).filter(JobSource.job_id == job.id).count()
    assert sources == 2
