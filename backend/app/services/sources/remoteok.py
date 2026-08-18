"""RemoteOK API — free, no key. Remote/tech-heavy listings (AI, EdTech, tutoring).

RemoteOK requires attribution/link-back when republishing; we keep the
original listing URL as source_url and never republish content wholesale.
"""
from __future__ import annotations

import logging

import httpx
from sqlalchemy.orm import Session

from .base import RawListing, SourceAdapter

logger = logging.getLogger("careerpilot.sources.remoteok")

USER_AGENT = "CareerPilotAI/0.2 (personal career assistant; contact: johngichaga8@gmail.com)"
URL = "https://remoteok.com/api"

# RemoteOK returns the whole feed per request — cache it briefly in-process
# so 26 query terms don't translate into 26 identical feed downloads.
_feed_cache: dict[str, tuple[float, list]] = {}
_FEED_TTL = 30 * 60  # seconds


class RemoteOKAdapter(SourceAdapter):
    name = "remoteok"
    kind = "API"

    def fetch(self, db: Session, query: str, limit: int = 20) -> list[RawListing]:  # noqa: ARG002
        import time as _time

        now = _time.monotonic()
        cached = _feed_cache.get("remoteok")
        if cached and now - cached[0] < _FEED_TTL:
            data = cached[1]
        else:
            try:
                resp = httpx.get(URL, headers={"User-Agent": USER_AGENT}, timeout=20)
                resp.raise_for_status()
                data = resp.json()
                _feed_cache["remoteok"] = (now, data)
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("RemoteOK request failed: %s", exc)
                return []

        q = query.lower()
        out: list[RawListing] = []
        # RemoteOK returns all jobs; filter client-side (their API has no search)
        for item in data:
            if not isinstance(item, dict):
                continue
            haystack = " ".join(
                str(item.get(k, "")) for k in ("position", "company", "tags", "description")
            ).lower()
            if q and q not in haystack:
                continue
            text = _render(item)
            if not text:
                continue
            out.append(
                RawListing(
                    title=item.get("position", ""),
                    url=item.get("url", ""),
                    raw_text=text,
                    source_name="remoteok",
                    source_type="API",
                    extra={"remoteok_id": item.get("id")},
                )
            )
            if len(out) >= limit:
                break
        return out


def _render(item: dict) -> str:
    parts = [item.get("position", ""), f"Company: {item.get('company', '')}"]
    if item.get("location"):
        parts.append(f"Location: {item['location']}")
    if item.get("salary"):
        parts.append(f"Salary: {item['salary']}")
    if item.get("tags"):
        parts.append("Tags: " + ", ".join(item["tags"]))
    desc = (item.get("description") or "").strip()
    if desc:
        parts.append("Description:\n" + desc[:6000])
    return "\n".join(p for p in parts if p)
