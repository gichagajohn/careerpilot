"""LLM provider tests — JSON parsing, fallbacks, error handling."""
from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.core.llm import GeminiProvider, LLMError, _parse_json_model


class _Out(BaseModel):
    title: str
    remote: bool = False
    salary_currency: str | None = None


def test_parse_plain_json():
    out = _parse_json_model('{"title": "Maths Teacher", "remote": true}', _Out)
    assert out.title == "Maths Teacher"
    assert out.remote is True


def test_parse_with_code_fence_and_noise():
    raw = 'Sure! Here is the JSON:\n```json\n{"title": "AI Evaluator", "salary_currency": "USD"}\n```\nHope this helps.'
    out = _parse_json_model(raw, _Out)
    assert out.title == "AI Evaluator"
    assert out.salary_currency == "USD"


def test_parse_invalid_json_raises():
    with pytest.raises(LLMError):
        _parse_json_model("not json at all", _Out)


def test_parse_validation_failure_raises():
    with pytest.raises(LLMError):
        _parse_json_model('{"wrong_field": 1}', _Out)


def test_gemini_requires_key():
    """Without GEMINI_API_KEY the provider must raise LLMError, not crash."""
    provider = GeminiProvider()
    with pytest.raises(LLMError):
        provider.complete_text("system", "user")
