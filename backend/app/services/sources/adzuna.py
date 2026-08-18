"""Adzuna Jobs API adapter — official, self-serve, free tier (~1,000 calls/month).

Covers Kenya via the /ke/ market (adzuna.co.ke) plus other configured
countries. We use a modest results_per_page and only 'core' queries to stay
well within the free quota (cadence is 'daily' by default).
"""
from __future__ import annotations

import logging

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings

from .base import RawListing, SourceAdapter

logger = logging.getLogger("careerpilot.sources.adzuna")

USER_AGENT = "CareerPilotAI/0.2 (personal career assistant; contact: johngichaga8@gmail.com)"
BASE_URL = "https://api.adzuna.com/v1/api/jobs"


class AdzunaAdapter(SourceAdapter):
    name = "adzuna"
    kind = "API"

    def fetch(self, db: Session, query: str, limit: int = 20) -> list[RawListing]:  # noqa: ARG002
        settings = get_settings()
        if not settings.adzuna_app_id or not settings.adzuna_app_key:
            logger.info("Adzuna skipped: ADZUNA_APP_ID / ADZUNA_APP_KEY not configured")
            return []

        out: list[RawListing] = []
        for country in settings.adzuna_countries:
            url = f"{BASE_URL}/{country}/search/1"
            params = {
                "app_id": settings.adzuna_app_id,
                "app_key": settings.adzuna_app_key,
                "what": query,
                "results_per_page": min(limit, 20),
                "content-type": "application/json",
                "max_days_old": 30,
            }
            try:
                resp = httpx.get(
                    url,
                    params=params,
                    headers={"User-Agent": USER_AGENT},
                    timeout=20,
                )
            except httpx.HTTPError as exc:
                logger.warning("Adzuna request failed (%s/%s): %s", country, query, exc)
                continue
            if resp.status_code == 401 or resp.status_code == 403:
                logger.warning("Adzuna auth failed (%s) — check ADZUNA_APP_ID/KEY", resp.status_code)
                continue
            if resp.status_code != 200:
                logger.info("Adzuna %s for %s/%s", resp.status_code, country, query)
                continue
            try:
                data = resp.json()
            except ValueError:
                continue
            for item in data.get("results", []):
                text = _render(item)
                if not text:
                    continue
                out.append(
                    RawListing(
                        title=item.get("title", ""),
                        url=item.get("redirect_url", ""),
                        raw_text=text,
                        source_name="adzuna",
                        source_type="API",
                        extra={"adzuna_id": item.get("id")},
                    )
                )
        return out


def _render(item: dict) -> str:
    parts = [
        item.get("title", ""),
        f"Company: {item.get('company', {}).get('display_name', '')}",
        f"Location: {item.get('location', {}).get('display_name', '')}",
    ]
    if item.get("salary_min") and item.get("salary_max"):
        parts.append(f"Salary: {item['salary_min']} - {item['salary_max']}")
    if item.get("contract_type"):
        parts.append(f"Contract type: {item['contract_type']}")
    if item.get("created"):
        parts.append(f"Posted: {item['created']}")
    desc = (item.get("description") or "").strip()
    if desc:
        parts.append("Description:\n" + desc[:8000])
    return "\n".join(p for p in parts if p)
