"""Arbeitnow API — free, no key. Europe-leaning job board feed (useful for
remote-friendly international/EdTech roles)."""
from __future__ import annotations

import logging

import httpx
from sqlalchemy.orm import Session

from .base import RawListing, SourceAdapter

logger = logging.getLogger("careerpilot.sources.arbeitnow")

USER_AGENT = "CareerPilotAI/0.2 (personal career assistant; contact: johngichaga8@gmail.com)"
URL = "https://www.arbeitnow.com/api/job-board-api"

# Whole-feed response — brief in-process cache (politeness + speed).
_feed_cache: dict[str, tuple[float, dict]] = {}
_FEED_TTL = 30 * 60  # seconds


class ArbeitnowAdapter(SourceAdapter):
    name = "arbeitnow"
    kind = "API"

    def fetch(self, db: Session, query: str, limit: int = 20) -> list[RawListing]:  # noqa: ARG002
        import time as _time

        now = _time.monotonic()
        cached = _feed_cache.get("arbeitnow")
        if cached and now - cached[0] < _FEED_TTL:
            data = cached[1]
        else:
            try:
                resp = httpx.get(URL, headers={"User-Agent": USER_AGENT}, timeout=20)
                resp.raise_for_status()
                data = resp.json()
                _feed_cache["arbeitnow"] = (now, data)
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("Arbeitnow request failed: %s", exc)
                return {}

        q = query.lower()
        out: list[RawListing] = []
        for item in data.get("data", [])[:200]:
            haystack = " ".join(
                str(item.get(k, "")) for k in ("title", "company_name", "tags")
            ).lower()
            if q and q not in haystack:
                continue
            text = _render(item)
            if not text:
                continue
            out.append(
                RawListing(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    raw_text=text,
                    source_name="arbeitnow",
                    source_type="API",
                    extra={"arbeitnow_slug": item.get("slug")},
                )
            )
            if len(out) >= limit:
                break
        return out


def _render(item: dict) -> str:
    parts = [item.get("title", ""), f"Company: {item.get('company_name', '')}"]
    if item.get("location"):
        parts.append(f"Location: {item['location']}")
    if item.get("tags"):
        parts.append("Tags: " + ", ".join(item["tags"]))
    if item.get("url"):
        parts.append(f"Apply: {item['url']}")
    return "\n".join(p for p in parts if p)
