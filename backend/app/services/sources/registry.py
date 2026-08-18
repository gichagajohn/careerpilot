"""Source registry — maps search_sources.name → adapter class."""
from __future__ import annotations

from .adzuna import AdzunaAdapter
from .arbeitnow import ArbeitnowAdapter
from .base import SourceAdapter
from .remoteok import RemoteOKAdapter
from .remotive import RemotiveAdapter
from .rss import RssAdapter
from .scholarship_pages import ScholarshipPagesAdapter
from .websearch import WebSearchAdapter

ADAPTERS: dict[str, type[SourceAdapter]] = {
    "adzuna": AdzunaAdapter,
    "remotive": RemotiveAdapter,
    "remoteok": RemoteOKAdapter,
    "arbeitnow": ArbeitnowAdapter,
    "websearch": WebSearchAdapter,
    "rss": RssAdapter,
    "scholarship_pages": ScholarshipPagesAdapter,
}
