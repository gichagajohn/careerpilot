"""Official scholarship programme pages — polite read-only fetches.

These rows are configured in search_sources with kind='FETCH',
category='scholarships' and an official programme URL. The PoliteFetcher
honours robots.txt, rate limits and caches for 24h. Pages that fail are
skipped silently (a programme page redesign must never break discovery).
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SearchSource
from app.services.polite import PoliteFetcher

from .base import RawListing, SourceAdapter

logger = logging.getLogger("careerpilot.sources.scholarship_pages")


class ScholarshipPagesAdapter(SourceAdapter):
    name = "scholarship_pages"
    kind = "FETCH"

    def fetch(self, db: Session, query: str | None = None, limit: int = 20) -> list[RawListing]:  # noqa: ARG002
        rows = db.scalars(
            select(SearchSource).where(
                SearchSource.kind == "FETCH",
                SearchSource.category == "scholarships",
                SearchSource.enabled.is_(True),
                SearchSource.url.isnot(None),
            )
        ).all()

        fetcher = PoliteFetcher(db)
        out: list[RawListing] = []
        for row in rows[:limit]:
            title, text = fetcher.fetch_text_and_title(row.url)
            if not text:
                logger.info("Scholarship page %s not fetched (robots/throttle/failure)", row.name)
                continue
            out.append(
                RawListing(
                    title=(title or row.name).strip(),
                    url=row.url,
                    raw_text=text,
                    source_name=f"page:{row.name}",
                    source_type="FETCH",
                    extra={"feed_url": row.url},
                )
            )
        return out
