"""Normalizer tests — deterministic fallback + mocked LLM path."""
from __future__ import annotations

from app.schemas.opportunities import JobIn
from app.services.normalizer import RawListing, normalize_listing

SAMPLE_TEXT = """Mathematics Teacher (IGCSE)
Company: Nairobi International Academy
Location: Nairobi, Kenya
Employment: Full-time
Salary: 120,000 KES - 150,000 KES per month
Deadline: 28 Aug 2026

Requirements:
- Bachelor of Education in Mathematics
- TSC registration
- Must have IGCSE experience

Preferred:
- CBC/CBE experience
- Familiarity with ICT tools
"""

REMOTE_AI_TEXT = """AI Mathematics Evaluator
AI Training Platform
Remote, work from home
Contract

We need experts in mathematics to evaluate AI model responses.
AI trainer, AI evaluator role. Data annotation tasks available.
"""


def test_deterministic_extraction():
    listing = RawListing(
        title="Mathematics Teacher (IGCSE)",
        url="https://example.com/job/1",
        raw_text=SAMPLE_TEXT,
        source_name="test",
        source_type="API",
    )
    normalized = normalize_listing(listing, use_llm=False)
    assert normalized is not None
    job = normalized.job
    assert job.title == "Mathematics Teacher (IGCSE)"
    assert job.organization_name == "Nairobi International Academy"
    assert job.location == "Nairobi, Kenya"
    assert job.employment_type == "Full-time"
    assert job.salary_currency == "KES"
    assert job.deadline == "28 Aug 2026"
    assert job.remote is False
    assert any("TSC" in r for r in job.requirements)
    assert any("CBC" in r for r in job.preferred_requirements)


def test_deterministic_remote_ai_detection():
    listing = RawListing(
        title="",  # must be derived from text
        url="https://example.com/job/2",
        raw_text=REMOTE_AI_TEXT,
        source_name="test",
        source_type="API",
    )
    job = normalize_listing(listing, use_llm=False).job
    assert job.remote is True
    assert job.is_ai_training is True
    assert job.employment_type == "Contract"
    assert job.title  # derived from text


def test_llm_path_used_when_available(monkeypatch):
    class FakeProvider:
        def complete_json(self, system, user, output_model, task="generic"):  # noqa: ARG002
            return output_model.model_validate(
                {"title": "Computer Science Teacher", "organization_name": "School X", "remote": True}
            )

    monkeypatch.setattr("app.services.normalizer.get_provider", lambda: FakeProvider())
    listing = RawListing("Maths Teacher", "https://example.com/job/3", "raw text here", "test", "API")
    job = normalize_listing(listing, use_llm=True).job
    assert job.title == "Computer Science Teacher"
    assert job.organization_name == "School X"
    assert job.remote is True


def test_llm_failure_falls_back_to_deterministic(monkeypatch):
    class _BoomProvider:
        def complete_json(self, system, user, output_model, task="generic"):  # noqa: ARG002
            raise RuntimeError("provider down")

    monkeypatch.setattr("app.services.normalizer.get_provider", lambda: _BoomProvider())
    listing = RawListing("Maths Teacher", "https://example.com/job/4", "Company: Test School\nRequirements: degree", "test", "API")
    job = normalize_listing(listing, use_llm=True).job
    assert job.title == "Maths Teacher"
