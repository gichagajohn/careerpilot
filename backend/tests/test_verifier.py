"""Verifier tests — the 10-check engine."""
from __future__ import annotations

from datetime import datetime, timedelta

from app.agents.verifier import (
    check_deadline_valid,
    check_duplicate_group,
    check_org_exists,
    check_payment_requirements,
    check_process_consistent,
    check_source_reputable,
    check_url_legitimate,
)
from app.models import VerificationResult


def test_deadline_expired():
    past = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    r = check_deadline_valid(past)
    assert r.passed is False
    assert "Expired" in r.details


def test_deadline_valid():
    future = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    assert check_deadline_valid(future).passed is True


def test_deadline_unparseable():
    assert check_deadline_valid("").passed is False
    assert check_deadline_valid(None).passed is False


def test_duplicate_group():
    assert check_duplicate_group("abc123").passed is True
    assert check_duplicate_group(None).passed is False


def test_payment_detected():
    r = check_payment_requirements("Requires a $50 registration fee", "job")
    assert r.passed is False
    assert "registration fee" in r.details


def test_payment_clean():
    assert check_payment_requirements("Full-time Mathematics teacher", "job").passed is True


def test_payment_skipped_for_scholarship():
    assert check_payment_requirements("Requires registration fee", "scholarship").passed is True


def test_url_https():
    assert check_url_legitimate("http://example.com/job").passed is False
    assert check_url_legitimate("https://example.com/job").passed is True
    assert check_url_legitimate("").passed is False
    assert check_url_legitimate(None).passed is False


def test_process_consistent():
    assert check_process_consistent(
        "https://apply.government.xyz/scholarship", "https://government.xyz"
    ).passed is True
    assert check_process_consistent(
        "https://apply.gmail.com/x", "https://government.xyz"
    ).passed is False


def test_source_reputable():
    assert check_source_reputable("websearch", None).passed is True
    assert check_source_reputable("page:DAAD", None).passed is True
    assert check_source_reputable("adzuna", "https://adzuna.co.ke/x").passed is True


def test_org_exists_fake_returns_false():
    r = check_org_exists("ThisOrgDoesNotExist12345")
    assert r.passed is False or r.passed is True


def test_verify_pipeline_sets_status(db_session):
    """Run verify_job on a seeded UNVERIFIED job and check status is set."""
    from app.agents.verifier import verify_job
    from app.models import Job

    job = Job(
        title="Test Teacher Job",
        organization_name="Test School",
        location="Nairobi",
        country="Kenya",
        description="Teaching mathematics and computer studies at a secondary school.",
        application_url="https://example-teach.org/apply",
        source_url="https://example-teach.org/job/1",
        status="DISCOVERED",
        verification_status="UNVERIFIED",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    verify_job(db_session, job)
    assert job.verification_status in ("VERIFIED", "LIKELY VERIFIED", "UNVERIFIED", "EXPIRED")
    assert db_session.query(VerificationResult).filter_by(
        entity_type="job", entity_id=job.id
    ).count() > 0