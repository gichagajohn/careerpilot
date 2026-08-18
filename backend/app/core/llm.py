"""LLM provider abstraction — free-first, provider-agnostic.

Supported providers (Phase 2):
  - gemini  : Google AI Studio free tier (Gemini 2.5 Flash), ~1,500 req/day
  - groq    : OpenAI-compatible endpoint, free tier (Llama models)
  - ollama  : fully local + free (OpenAI-compatible API)

Every call is logged to llm_usage_log so real token spend is visible
(cost_estimate stays 0.0 for the free-tier providers used in Phase 2).

Usage pattern (see agents/normalizer):
    from app.core.llm import get_provider, LLMError
    try:
        result = get_provider().complete_json(system, user, JobIn)
    except LLMError:
        result = fallback_extractor(...)   # deterministic no-LLM path
"""
from __future__ import annotations

import json
import logging
import re
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import LlmUsageLog

logger = logging.getLogger("careerpilot.llm")

TModel = TypeVar("TModel", bound=BaseModel)

USER_AGENT = "CareerPilotAI/0.2 (personal career assistant; contact: johngichaga8@gmail.com)"


class LLMError(RuntimeError):
    """Raised when a provider is unavailable or returns unusable output."""


def _log_usage(provider: str, model: str, task: str, in_tokens: int, out_tokens: int) -> None:
    try:
        with SessionLocal() as db:
            db.add(
                LlmUsageLog(
                    provider=provider,
                    model=model,
                    task=task,
                    input_tokens=in_tokens,
                    output_tokens=out_tokens,
                    cost_estimate=0.0,  # free-tier providers (Phase 2)
                )
            )
            db.commit()
    except Exception:  # pragma: no cover - telemetry must never break the pipeline
        logger.warning("Failed to log LLM usage", exc_info=True)


def _parse_json_model(raw: str, output_model: type[TModel]) -> TModel:
    """Extract the first JSON object from a model response and validate it."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise LLMError(f"No JSON object in model output: {raw[:200]!r}")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMError(f"Model returned invalid JSON: {exc}") from exc
    try:
        return output_model.model_validate(data)
    except ValidationError as exc:
        raise LLMError(f"Model JSON failed validation: {exc}") from exc


class LLMProvider:
    """Base class. Subclasses implement complete_json / complete_text."""

    name: str = "base"
    model: str = "unknown"

    def complete_json(self, system: str, user: str, output_model: type[TModel], task: str = "generic") -> TModel:  # noqa: ARG002
        raise NotImplementedError

    def complete_text(self, system: str, user: str, task: str = "generic") -> str:  # noqa: ARG002
        raise NotImplementedError


class GeminiProvider(LLMProvider):
    name = "gemini"
    model = "gemini-2.5-flash"
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models"

    def _call(self, system: str, user: str, json_mode: bool, task: str) -> str:
        settings = get_settings()
        if not settings.gemini_api_key:
            raise LLMError("GEMINI_API_KEY is not configured")
        body: dict = {
            "contents": [{"role": "user", "parts": [{"text": f"{system}\n\n{user}"}]}],
            "generationConfig": {"temperature": 0.0},
        }
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        try:
            resp = httpx.post(
                f"{self.endpoint}/{self.model}:generateContent",
                params={"key": settings.gemini_api_key},
                json=body,
                headers={"User-Agent": USER_AGENT},
                timeout=60,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMError(f"Gemini request failed: {exc}") from exc
        data = resp.json()
        usage = data.get("usageMetadata", {})
        _log_usage(
            self.name, self.model, task,
            usage.get("promptTokenCount", 0),
            usage.get("candidatesTokenCount", 0),
        )
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Unexpected Gemini response shape: {data}") from exc

    def complete_json(self, system: str, user: str, output_model: type[TModel], task: str = "generic") -> TModel:
        return _parse_json_model(self._call(system, user, True, task), output_model)

    def complete_text(self, system: str, user: str, task: str = "generic") -> str:
        return self._call(system, user, False, task)


class OpenAICompatProvider(LLMProvider):
    """Groq / Ollama share the OpenAI chat-completions contract."""

    name = "openai_compat"
    model = "llama-3.3-70b-versatile"
    base_url = ""

    def __init__(self, name: str, model: str, base_url: str, api_key: str | None = None) -> None:
        self.name = name
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key

    def _call(self, system: str, user: str, json_mode: bool, task: str) -> str:
        headers = {"User-Agent": USER_AGENT}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        body: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.0,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            resp = httpx.post(
                f"{self.base_url}/chat/completions", json=body, headers=headers, timeout=60
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMError(f"{self.name} request failed: {exc}") from exc
        data = resp.json()
        usage = data.get("usage", {})
        _log_usage(
            self.name, self.model, task,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
        )
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Unexpected {self.name} response shape: {data}") from exc

    def complete_json(self, system: str, user: str, output_model: type[TModel], task: str = "generic") -> TModel:
        return _parse_json_model(self._call(system, user, True, task), output_model)

    def complete_text(self, system: str, user: str, task: str = "generic") -> str:
        return self._call(system, user, False, task)


def get_provider() -> LLMProvider:
    """Instantiate the configured provider, with a fallback chain."""
    settings = get_settings()
    order = [settings.llm_provider, "gemini", "groq", "ollama"]
    tried: set[str] = set()
    for name in order:
        if name in tried:
            continue
        tried.add(name)
        if name == "gemini":
            return GeminiProvider()
        if name == "groq":
            return OpenAICompatProvider(
                name="groq",
                model="llama-3.3-70b-versatile",
                base_url="https://api.groq.com/openai/v1",
                api_key=settings.groq_api_key,
            )
        if name == "ollama":
            return OpenAICompatProvider(
                name="ollama",
                model="llama3.1",
                base_url=settings.ollama_base_url,
            )
    raise LLMError("No usable LLM provider configured")
