"""Scholarship normalizer tests — 19-field capture + funding evidence rule."""
from __future__ import annotations

from app.schemas.opportunities import ScholarshipIn
from app.services.normalizer import (
    RawListing,
    assess_funding,
    normalize_scholarship_listing,
)

FULLY_FUNDED_TEXT = """DAAD Master's Scholarship in Mathematics Education
University: University of Nairobi
Country: Germany
This fully funded scholarship covers full tuition, a monthly living allowance/stipend,
accommodation, health insurance and travel costs.
Eligible: Kenyan graduates with a First Class Honours degree.
IELTS 6.5 required. Age under 35.
Deadline: 31 October 2026
"""

PARTIAL_TEXT = """Erasmus Mundus Joint Master
European universities
Tuition coverage only for selected students. Partial funding available.
Open to African applicants.
Apply by 2027-01-15
"""


def test_deterministic_fully_funded_extraction():
    listing = RawListing(
        title="DAAD Master's Scholarship",
        url="https://www.daad.de/en/apply",
        raw_text=FULLY_FUNDED_TEXT,
        source_name="test",
        source_type="FETCH",
        extra={"feed_url": "https://www.daad.de/en/study-and-research-in-germany/scholarships/"},
    )
    sch = normalize_scholarship_listing(listing, use_llm=False).scholarship
    assert sch.name == "DAAD Master's Scholarship"
    assert sch.funding_level == "FULLY FUNDED"          # evidence present
    assert sch.open_to_kenyans is True
    assert sch.open_to_africans is False                # text mentions Kenya, not Africa
    assert sch.degree_level == "Master's"
    assert sch.deadline == "31 October 2026"
    assert sch.required_classification is not None
    assert sch.english_requirement is not None
    assert sch.accommodation == "Yes"
    assert sch.living_allowance == "Yes"


def test_funding_downgraded_without_evidence():
    """A listing that only mentions tuition must NOT be marked fully funded."""
    listing = RawListing(
        title="Some Master's Scholarship",
        url="https://example.com/s",
        raw_text="Partial funding. Tuition coverage for selected students. Apply by 2027-01-15.",
        source_name="test",
        source_type="SEARCH",
    )
    sch = normalize_scholarship_listing(listing, use_llm=False).scholarship
    assert sch.funding_level != "FULLY FUNDED"
    assert sch.funding_level in ("TUITION-ONLY", "PARTIAL", "UNSPECIFIED")


def test_assess_funding_rules():
    assert assess_funding("fully funded scholarship", None) == "FULLY FUNDED"
    assert assess_funding("full tuition + stipend + accommodation provided", None) == "FULLY FUNDED"
    assert assess_funding("full tuition only", None) == "TUITION-ONLY"
    assert assess_funding("tuition-free program", None) == "TUITION-FREE"
    assert assess_funding("partial funding", None) == "PARTIAL"
    assert assess_funding("some benefits", None) == "UNSPECIFIED"
    # conservative: LLM claimed FULLY FUNDED but text has no evidence → downgraded
    assert assess_funding("a scholarship", "FULLY FUNDED") != "FULLY FUNDED"


def test_llm_path_used_when_available(monkeypatch):
    class _Fake:
        def complete_json(self, system, user, output_model, task="generic"):  # noqa: ARG002
            return output_model.model_validate(
                {"name": "Chevening Scholarship", "university": "UK universities",
                 "funding_level": "FULLY FUNDED", "open_to_kenyans": True}
            )

    monkeypatch.setattr("app.services.normalizer.get_provider", lambda: _Fake())
    listing = RawListing("Chevening", "https://chevening.org/scholarships/",
                         "Chevening Scholarships. Fully funded.", "test", "FETCH")
    sch = normalize_scholarship_listing(listing, use_llm=True).scholarship
    assert sch.name == "Chevening Scholarship"
    assert sch.open_to_kenyans is True
    # funding survives because the text itself contains the evidence
    assert sch.funding_level == "FULLY FUNDED"


def test_llm_false_claim_blocked(monkeypatch):
    """LLM claims FULLY FUNDED but the source text has no evidence → downgraded."""
    class _Lying:
        def complete_json(self, system, user, output_model, task="generic"):  # noqa: ARG002
            return output_model.model_validate(
                {"name": "Mystery Grant", "funding_level": "FULLY FUNDED"}
            )

    monkeypatch.setattr("app.services.normalizer.get_provider", lambda: _Lying())
    listing = RawListing("Mystery Grant", "https://example.com/g",
                         "A small grant for students.", "test", "SEARCH")
    sch = normalize_scholarship_listing(listing, use_llm=True).scholarship
    assert sch.funding_level != "FULLY FUNDED"
