"""Polite web fetcher — respects robots.txt, rate limits and caches results.

Used for read-only page fetching (job listings, scholarship pages). It never
bypasses access controls and it caches page content for 24h to avoid
re-fetching unchanged pages (spec §15: no aggressive scraping).
"""
from __future__ import annotations

import hashlib
import logging
import time
import urllib.robotparser
from datetime import datetime, timedelta
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ResultCache

logger = logging.getLogger("careerpilot.polite")

USER_AGENT = "CareerPilotAI/0.2 (personal career assistant; contact: johngichaga8@gmail.com)"
MIN_INTERVAL_SECONDS = 1.0  # polite per-domain rate limit
MAX_BYTES = 2 * 1024 * 1024
CACHE_TTL_HOURS = 24


class PoliteFetcher:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._last_fetch: dict[str, float] = {}

    # ── robots.txt ────────────────────────────────────────────
    def _robots_parser(self, url: str) -> urllib.robotparser.RobotFileParser | None:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain in self._robots:
            return self._robots[domain]
        parser = None
        try:
            parser = urllib.robotparser.RobotFileParser()
            parser.set_url(f"{parsed.scheme}://{domain}/robots.txt")
            parser.read()
        except Exception:
            logger.warning("Could not read robots.txt for %s", domain)
            parser = None
        self._robots[domain] = parser
        return parser

    def allowed(self, url: str) -> bool:
        parser = self._robots_parser(url)
        if parser is None:
            return True  # no robots.txt → treat as allowed, still rate-limited
        try:
            return parser.can_fetch(USER_AGENT, url)
        except Exception:
            return False

    # ── rate limiting ─────────────────────────────────────────
    def _throttle(self, url: str) -> None:
        domain = urlparse(url).netloc.lower()
        last = self._last_fetch.get(domain, 0.0)
        wait = MIN_INTERVAL_SECONDS - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
        self._last_fetch[domain] = time.monotonic()

    # ── cache ─────────────────────────────────────────────────
    def _cache_get(self, url: str, content_hash: str) -> bool:
        cutoff = (datetime.now().astimezone() - timedelta(hours=CACHE_TTL_HOURS)).isoformat(
            timespec="seconds"
        )
        row = self.db.scalar(
            select(ResultCache).where(
                ResultCache.url == url,
                ResultCache.content_hash == content_hash,
                ResultCache.fetched_at >= cutoff,
            )
        )
        return row is not None

    def _cache_put(self, url: str, content_hash: str) -> None:
        self.db.add(
            ResultCache(
                source_type="fetch",
                query=None,
                url=url,
                content_hash=content_hash,
            )
        )
        self.db.commit()

    # ── fetch ─────────────────────────────────────────────────
    def fetch_text(self, url: str, timeout: float = 12.0) -> str | None:
        """Fetch a page's text if robots allow, rate limits permit, and cache misses."""
        return self._fetch(url, timeout)[1]

    def fetch_text_and_title(self, url: str, timeout: float = 12.0) -> tuple[str | None, str | None]:
        """Fetch a page's (title, text); both None if the fetch was skipped/failed."""
        return self._fetch(url, timeout)

    def _fetch(self, url: str, timeout: float) -> tuple[str | None, str | None]:
        if not url or not url.startswith("http"):
            return None, None
        if not self.allowed(url):
            logger.info("robots.txt disallows fetch: %s", url)
            return None, None
        content_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
        if self._cache_get(url, content_hash):
            return None, None  # unchanged/already fetched today — skip
        self._throttle(url)
        try:
            resp = httpx.get(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
                follow_redirects=True,
                timeout=timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.info("Fetch failed for %s: %s", url, exc)
            return None, None
        if len(resp.content) > MAX_BYTES:
            logger.info("Skipping oversized page: %s (%d bytes)", url, len(resp.content))
            return None, None
        self._cache_put(url, content_hash)
        return _extract_title(resp.text), _plain_text(resp.text)


def _extract_title(html: str) -> str | None:
    import re

    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    if not m:
        return None
    title = re.sub(r"\s+", " ", m.group(1)).strip()
    return title[:200] or None


def _plain_text(html: str) -> str:
    """Very light HTML→text conversion (keeps cost down; LLM handles the rest)."""
    import re

    text = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", html)
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</(p|div|li|h[1-6]|tr)>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()[:20_000]
