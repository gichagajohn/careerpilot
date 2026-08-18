"""RSS adapter — reads feeds configured in the search_sources table.

Feeds are the politest source there is: publishers provide them for exactly
this purpose. Feed URLs are user-configurable (e.g. ReliefWeb education jobs,
UN Careers, a school's blog/feed).
"""
from __future__ import annotations

import logging

import feedparser
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SearchSource

from .base import RawListing, SourceAdapter

logger = logging.getLogger("careerpilot.sources.rss")


class RssAdapter(SourceAdapter):
    name = "rss"
    kind = "RSS"

    def fetch(self, db: Session, query: str, limit: int = 30) -> list[RawListing]:  # noqa: ARG002
        feeds = db.scalars(
            select(SearchSource).where(
                SearchSource.kind == "RSS",
                SearchSource.enabled.is_(True),
                SearchSource.url.isnot(None),
            )
        ).all()

        out: list[RawListing] = []
        for feed in feeds:
            try:
                parsed = feedparser.parse(feed.url, agent=USER_AGENT)
            except Exception as exc:  # feedparser rarely raises; guard anyway
                logger.warning("RSS parse failed for %s: %s", feed.url, exc)
                continue
            status = getattr(parsed, "status", None)
            if status in (202, 429):
                # publisher throttling / queueing — try again on the next run
                logger.info("RSS feed %s throttled (HTTP %s); skipping this run", feed.name, status)
                continue
            if getattr(parsed, "bozo", False):
                logger.info("RSS feed %s reported an issue: %s", feed.name, parsed.bozo_exception)
            for entry in parsed.entries[:limit]:
                title = getattr(entry, "title", "") or ""
                link = getattr(entry, "link", "")
                summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
                if not title and not summary:
                    continue
                out.append(
                    RawListing(
                        title=title,
                        url=link,
                        raw_text=f"{title}\n{summary}",
                        source_name=f"rss:{feed.name}",
                        source_type="RSS",
                        extra={"feed_url": feed.url},
                    )
                )
        return out


USER_AGENT = "CareerPilotAI/0.2 (personal career assistant; contact: johngichaga8@gmail.com)"
