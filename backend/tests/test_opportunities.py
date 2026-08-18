"""Opportunity (job / scholarship) and application tracker tests."""
from __future__ import annotations


def test_job_crud_and_filters(client, auth_headers):
    # create
    r = client.post(
        "/api/v1/jobs",
        json={
            "title": "Mathematics Teacher",
            "organization_name": "Nova Pioneer",
            "location": "Nairobi, Kenya",
            "employment_type": "Full-time",
            "requirements": ["B.Ed Mathematics", "TSC registration"],
            "preferred_requirements": ["CBC/CBE"],
            "deadline": "2026-08-28",
            "application_url": "https://example.com/apply",
        },
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["verification_status"] == "UNVERIFIED"
    assert job["status"] == "DISCOVERED"
    job_id = job["id"]

    # list
    r = client.get("/api/v1/jobs", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1

    # filter by verification status
    r = client.get("/api/v1/jobs", params={"verification_status": "VERIFIED"}, headers=auth_headers)
    assert r.json() == []

    # update (agents will PATCH verification/match scores later)
    r = client.patch(
        f"/api/v1/jobs/{job_id}",
        json={"verification_status": "VERIFIED", "match_score": 92.0, "priority_score": 85.0},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["verification_status"] == "VERIFIED"
    assert r.json()["match_score"] == 92.0

    # filter by match
    r = client.get("/api/v1/jobs", params={"min_match": 80}, headers=auth_headers)
    assert len(r.json()) == 1
    r = client.get("/api/v1/jobs", params={"min_match": 95}, headers=auth_headers)
    assert r.json() == []

    # missing job
    assert client.get("/api/v1/jobs/9999", headers=auth_headers).status_code == 404


def test_job_sources_deduplication_support(client, auth_headers):
    r = client.post(
        "/api/v1/jobs",
        json={"title": "Computer Studies Teacher", "organization_name": "School A"},
        headers=auth_headers,
    )
    job_id = r.json()["id"]

    r = client.post(
        f"/api/v1/jobs/{job_id}/sources",
        params={"source_type": "API", "source_name": "Adzuna", "source_url": "https://adzuna.co.ke/x"},
        headers=auth_headers,
    )
    assert r.json()["added"] is True
    # duplicate source rejected
    r = client.post(
        f"/api/v1/jobs/{job_id}/sources",
        params={"source_type": "API", "source_name": "Adzuna", "source_url": "https://adzuna.co.ke/x"},
        headers=auth_headers,
    )
    assert r.json()["added"] is False


def test_scholarship_crud(client, auth_headers):
    r = client.post(
        "/api/v1/scholarships",
        json={
            "name": "Erasmus Mundus Joint Master",
            "university": "European consortium",
            "country": "Europe",
            "programme": "Educational Technology",
            "degree_level": "Master's",
            "funding_level": "FULLY FUNDED",
            "tuition_coverage": "Full tuition",
            "deadline": "2027-01-15",
            "open_to_kenyans": True,
        },
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    sch = r.json()
    assert sch["funding_level"] == "FULLY FUNDED"
    sch_id = sch["id"]

    r = client.get("/api/v1/scholarships", params={"funding_level": "FULLY"}, headers=auth_headers)
    assert len(r.json()) == 1

    r = client.patch(
        f"/api/v1/scholarships/{sch_id}",
        json={"verification_status": "LIKELY VERIFIED", "match_score": 94.0},
        headers=auth_headers,
    )
    assert r.json()["match_score"] == 94.0


def test_application_tracker_flow(client, auth_headers):
    # opportunity
    r = client.post(
        "/api/v1/jobs",
        json={"title": "AI Mathematics Trainer", "organization_name": "EdTech Co",
              "remote": True, "is_ai_training": True},
        headers=auth_headers,
    )
    job_id = r.json()["id"]

    # create application
    r = client.post(
        "/api/v1/applications",
        json={"job_id": job_id, "status": "SHORTLISTED BY AGENT", "match_score": 90.0},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    app_id = r.json()["id"]

    # missing job_id + scholarship_id
    assert (
        client.post("/api/v1/applications", json={}, headers=auth_headers).status_code == 422
    )

    # status transitions (spec §11) + auto date_applied
    r = client.patch(
        f"/api/v1/applications/{app_id}",
        json={"status": "APPLIED"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "APPLIED"
    assert body["date_applied"] is not None

    r = client.patch(
        f"/api/v1/applications/{app_id}",
        json={"status": "INTERVIEW", "interview_date": "2026-09-10", "follow_up_date": "2026-09-01"},
        headers=auth_headers,
    )
    assert r.json()["status"] == "INTERVIEW"

    # audit events recorded
    r = client.get(f"/api/v1/applications/{app_id}", headers=auth_headers)
    events = [e["event_type"] for e in r.json()["events"]]
    assert "STATUS_CHANGED" in events

    # list filtered
    r = client.get("/api/v1/applications", params={"status_filter": "INTERVIEW"}, headers=auth_headers)
    assert len(r.json()) == 1
