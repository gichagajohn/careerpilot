"""Prompt template loader — one YAML file per task (spec §20).

Files live in app/prompts/ and are loaded lazily and cached. Each template
contains: system prompt, temperature, model tier, and guardrails.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@lru_cache(maxsize=32)
def load_prompt(name: str) -> dict:
    path = PROMPTS_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def build_message(prompt_name: str, **kwargs) -> tuple[str, str]:
    """Return (system, user) message pair from a template + variables."""
    template = load_prompt(prompt_name)
    system = template.get("system", "").strip()
    user = template.get("user_template", "").strip()
    if not user:
        raise ValueError(f"Prompt {prompt_name!r} has no user_template")
    try:
        rendered = user.format(**kwargs)
    except KeyError as exc:
        raise ValueError(f"Prompt {prompt_name!r} missing variable: {exc}") from exc
    return system, rendered
