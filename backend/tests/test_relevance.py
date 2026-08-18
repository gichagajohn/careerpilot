"""Relevance gate tests."""
from __future__ import annotations

from app.services.normalizer import RawListing
from app.services.relevance import is_relevant, is_relevant_scholarship


def _listing(title: str, text: str = "") -> RawListing:
    return RawListing(title=title, url="https://example.com/x", raw_text=text,
                      source_name="test", source_type="API")


def test_keeps_teaching_and_ai_training():
    assert is_relevant(_listing("Mathematics Teacher", "Teach IGCSE Mathematics at a school."))
    assert is_relevant(_listing("AI Evaluator", "Evaluate AI model outputs for mathematics."))
    assert is_relevant(_listing("Data Labeling Specialist", "Label data for AI training."))
    assert is_relevant(_listing("Instructional Designer", "Design curriculum."))
    assert is_relevant(_listing("Computer Science Teacher"))
    assert is_relevant(_listing("Curriculum Developer"))


def test_drops_obvious_out_of_scope():
    assert not is_relevant(_listing("Sales Jedi", "Drive revenue growth."))
    assert not is_relevant(_listing("Freelance Copywriter"))
    assert not is_relevant(_listing("Senior Graphic Designer"))
    assert not is_relevant(_listing("Head of Marketing"))
    assert not is_relevant(_listing("Tech Lead Full-Stack Rails Engineer",
                                    "JavaScript, Python, Ruby on Rails, AI/ML, advertising."))
    assert not is_relevant(_listing("SaaS Product Support Jedi", "Support customers with Python tooling."))
    assert not is_relevant(_listing("Senior Independent AI Engineer", "Design AI architectures."))


def test_scholarship_gate_keeps_and_drops():
    assert is_relevant_scholarship(_listing("DAAD Master's Scholarship 2027"))
    assert is_relevant_scholarship(_listing("Fully Funded Fellowship in AI"))
    assert is_relevant_scholarship(_listing("ACET Graduate Intern 2026", "Fully funded career opportunity with stipend."))
    assert not is_relevant_scholarship(_listing("ICC Translation Officer Job"))
    assert not is_relevant_scholarship(_listing("Youth Climate Creative Workshops"))
