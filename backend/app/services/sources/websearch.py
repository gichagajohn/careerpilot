"""Web search adapter — Google CSE / Serper / Tavily (discovery only).

This is the *polite* way to cover sources we must not scrape directly
(LinkedIn, Indeed, TES, BrighterMonday, Fuzu, MyJobMag, Teacher Horizons...).
We get search snippets + links, then politely fetch the top candidates' pages
(robots.txt + rate limits + 24h cache). We never log into, or automate
against, those platforms here — application assistance is a separate,
human-gated phase (Phase 9).
"""
from __future__ import annotations

import logging

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.polite import PoliteFetcher

from .base import RawListing, SourceAdapter

logger = logging.getLogger("careerpilot.sources.websearch")

USER_AGENT = "CareerPilotAI/0.2 (personal career assistant; contact: johngichaga8@gmail.com)"
ENRICH_LIMIT = 3  # polite page fetches per query


class WebSearchAdapter(SourceAdapter):
    name = "websearch"
    kind = "SEARCH"

    def fetch(self, db: Session, query: str, limit: int = 8) -> list[RawListing]:
        settings = get_settings()
        hits: list[dict] = []

        if settings.google_cse_key and settings.google_cse_cx:
            hits += self._google_cse(query)
        elif settings.serper_key:
            hits += self._serper(query)
        elif settings.tavily_key:
            hits += self._tavily(query)
        else:
            logger.info("WebSearch skipped: no search API key configured")

        # de-duplicate hits by URL within this batch
        seen: set[str] = set()
        uniq: list[dict] = []
        for h in hits:
            url = h.get("url", "")
            if not url or url in seen:
                continue
            seen.add(url)
            uniq.append(h)

        fetcher = PoliteFetcher(db)
        out: list[RawListing] = []
        for idx, hit in enumerate(uniq[:limit]):
            raw_text = hit.get("snippet") or ""
            if idx < ENRICH_LIMIT:
                fetched = fetcher.fetch_text(hit["url"])
                if fetched:
                    raw_text = f"{hit.get('snippet') or ''}\n\n{fetched}"[:20_000]
            if not raw_text and not hit.get("title"):
                continue
            out.append(
                RawListing(
                    title=hit.get("title", ""),
                    url=hit["url"],
                    raw_text=raw_text,
                    source_name="websearch",
                    source_type="SEARCH",
                    extra={"engine": hit.get("engine")},
                )
            )
        return out

    # ── engines ───────────────────────────────────────────────
    def _google_cse(self, query: str) -> list[dict]:
        settings = get_settings()
        try:
            resp = httpx.get(
                "https://www.googleapis.com/customsearch/v1",
                params={
                    "key": settings.google_cse_key,
                    "cx": settings.google_cse_cx,
                    "q": query,
                    "num": 8,
                },
                headers={"User-Agent": USER_AGENT},
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Google CSE request failed (%s): %s", query, exc)
            return []
        return [
            {"title": item.get("title", ""), "url": item.get("link", ""), "snippet": item.get("snippet", ""), "engine": "google_cse"}
            for item in data.get("items", [])
            if item.get("link")
        ]

    def _serper(self, query: str) -> list[dict]:
        settings = get_settings()
        try:
            resp = httpx.post(
                "https://google.serper.dev/search",
                json={"q": query, "num": 8},
                headers={"X-API-KEY": settings.serper_key, "User-Agent": USER_AGENT},
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Serper request failed (%s): %s", query, exc)
            return []
        return [
            {"title": item.get("title", ""), "url": item.get("link", ""), "snippet": item.get("snippet", ""), "engine": "serper"}
            for item in data.get("organic", [])
            if item.get("link")
        ]

    def _tavily(self, query: str) -> list[dict]:
        settings = get_settings()
        try:
            resp = httpx.post(
                "https://api.tavily.com/search",
                json={"api_key": settings.tavily_key, "query": query, "max_results": 8},
                headers={"User-Agent": USER_AGENT},
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Tavily request failed (%s): %s", query, exc)
            return []
        return [
            {"title": item.get("title", ""), "url": item.get("url", ""), "snippet": item.get("content", ""), "engine": "tavily"}
            for item in data.get("results", [])
            if item.get("url")
        ]
