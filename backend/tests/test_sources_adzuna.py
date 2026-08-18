"""Adzuna adapter test with mocked HTTP (official API shape)."""
from __future__ import annotations


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")
        return None

    def json(self):
        return self._payload


class _FakeSettings:
    adzuna_app_id = "test_id"
    adzuna_app_key = "test_key"
    adzuna_countries = ["ke"]


def test_adzuna_fetch_parses_listings(monkeypatch, db_session):
    payload = {
        "results": [
            {
                "id": "abc123",
                "title": "Mathematics Teacher",
                "company": {"display_name": "Nairobi International Academy"},
                "location": {"display_name": "Nairobi"},
                "description": "Teach Mathematics IGCSE. Requirements: B.Ed Maths, TSC.",
                "salary_min": 120000,
                "salary_max": 150000,
                "contract_type": "permanent",
                "redirect_url": "https://www.adzuna.co.ke/land/abc123",
                "created": "2026-08-10T09:00:00Z",
            }
        ]
    }
    monkeypatch.setattr("app.services.sources.adzuna.get_settings", lambda: _FakeSettings())
    monkeypatch.setattr(
        "app.services.sources.adzuna.httpx.get",
        lambda *a, **k: _FakeResponse(200, payload),
    )

    from app.services.sources.adzuna import AdzunaAdapter

    listings = AdzunaAdapter().fetch(db_session, "Mathematics Teacher")
    assert len(listings) == 1
    listing = listings[0]
    assert listing.title == "Mathematics Teacher"
    assert "Nairobi International Academy" in listing.raw_text
    assert "Salary: 120000 - 150000" in listing.raw_text
    assert listing.source_name == "adzuna"
    assert listing.source_type == "API"
    assert listing.extra["adzuna_id"] == "abc123"


def test_adzuna_skipped_without_keys(monkeypatch, db_session):
    class _NoKeys:
        adzuna_app_id = ""
        adzuna_app_key = ""
        adzuna_countries = ["ke"]

    monkeypatch.setattr("app.services.sources.adzuna.get_settings", lambda: _NoKeys())
    from app.services.sources.adzuna import AdzunaAdapter

    assert AdzunaAdapter().fetch(db_session, "Mathematics Teacher") == []


def test_adzuna_auth_failure_logged(monkeypatch, db_session):
    monkeypatch.setattr("app.services.sources.adzuna.get_settings", lambda: _FakeSettings())
    monkeypatch.setattr(
        "app.services.sources.adzuna.httpx.get",
        lambda *a, **k: _FakeResponse(401, {}),
    )
    from app.services.sources.adzuna import AdzunaAdapter

    assert AdzunaAdapter().fetch(db_session, "Mathematics Teacher") == []
