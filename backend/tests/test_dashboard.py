"""Dashboard summary tests."""
from __future__ import annotations


def test_dashboard_summary_empty(client, auth_headers):
    r = client.get("/api/v1/dashboard/summary", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total_opportunities"] == 0
    assert body["upcoming_deadlines"] == []


def test_dashboard_summary_counts(client, auth_headers):
    # two jobs (one high-match, one with near deadline), one scholarship
    client.post(
        "/api/v1/jobs",
        json={"title": "Mathematics Teacher", "organization_name": "School A",
              "deadline": "2026-08-28", "match_score": 92.0},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/jobs",
        json={"title": "ICT Teacher", "organization_name": "School B", "deadline": "2030-01-01"},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/scholarships",
        json={"name": "DAAD Masters", "university": "German university",
              "deadline": "2026-08-25", "match_score": 88.0},
        headers=auth_headers,
    )

    r = client.get("/api/v1/dashboard/summary", headers=auth_headers)
    body = r.json()
    assert body["total_opportunities"] == 3
    assert body["scholarships_total"] == 1
    assert body["high_match_opportunities"] == 2

    upcoming = body["upcoming_deadlines"]
    # dates within the next 14 days from "now" — use relative dates to stay robust
    from datetime import date, timedelta

    near = (date.today() + timedelta(days=3)).isoformat()
    client.post(
        "/api/v1/jobs",
        json={"title": "CS Teacher", "organization_name": "School C", "deadline": near},
        headers=auth_headers,
    )
    r = client.get("/api/v1/dashboard/summary", headers=auth_headers)
    body = r.json()
    kinds = {d["kind"] for d in body["upcoming_deadlines"]}
    assert "job" in kinds
