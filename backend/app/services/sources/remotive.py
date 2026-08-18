"""Remotive Remote Jobs API — free, no key required, remote-only focus.

Ideal for remote teaching / AI-training / EdTech roles (spec categories 6–7, 18–24).
"""
from __future__ import annotations

import logging

import httpx
from sqlalchemy.orm import Session

from .base import RawListing, SourceAdapter

logger = logging.getLogger("careerpilot.sources.remotive")

USER_AGENT = "CareerPilotAI/0.2 (personal career assistant; contact: johngichaga8@gmail.com)"
URL = "https://remotive.com/api/remote-jobs"


class RemotiveAdapter(SourceAdapter):
    name = "remotive"
    kind = "API"

    def fetch(self, db: Session, query: str, limit: int = 20) -> list[RawListing]:  # noqa: ARG002
        try:
            resp = httpx.get(
                URL,
                params={"search": query, "limit": min(limit, 50)},
                headers={"User-Agent": USER_AGENT},
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Remotive request failed (%s): %s", query, exc)
            return []

        out: list[RawListing] = []
        for item in data.get("jobs", [])[:limit]:
            text = _render(item)
            if not text:
                continue
            out.append(
                RawListing(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    raw_text=text,
                    source_name="remotive",
                    source_type="API",
                    extra={"remotive_id": item.get("id")},
                )
            )
        return out


def _render(item: dict) -> str:
    parts = [
        item.get("title", ""),
        f"Company: {item.get('company_name', '')}",
        f"Location: {item.get('candidate_required_location', '')}",
    ]
    if item.get("job_type"):
        parts.append(f"Job type: {item['job_type']}")
    if item.get("salary"):
        parts.append(f"Salary: {item['salary']}")
    if item.get("tags"):
        parts.append("Tags: " + ", ".join(item["tags"]))
    if item.get("publication_date"):
        parts.append(f"Posted: {item['publication_date']}")
    return "\n".join(p for p in parts if p)
