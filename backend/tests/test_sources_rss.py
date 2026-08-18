"""RSS adapter tests with a mocked feedparser."""
from __future__ import annotations

from app.models import SearchSource


class _Entry:
    title = "Education Specialist - Nairobi"
    link = "https://example.org/jobs/1"
    summary = "Teach mathematics and ICT in Kakuma refugee camp."


class _Feed:
    bozo = False
    status = 200
    entries = [_Entry()]


class _EmptyFeed:
    bozo = False
    status = 202  # throttled — like ReliefWeb under load
    entries = []


def test_rss_parses_entries(monkeypatch, db_session):
    db_session.add(
        SearchSource(name="test-feed", kind="RSS", category="jobs",
                     url="https://example.org/feed", enabled=True, cadence="2x")
    )
    db_session.commit()

    monkeypatch.setattr("app.services.sources.rss.feedparser.parse", lambda *a, **k: _Feed())
    from app.services.sources.rss import RssAdapter

    listings = RssAdapter().fetch(db_session, "education")
    assert len(listings) == 1
    assert listings[0].title == "Education Specialist - Nairobi"
    assert listings[0].source_type == "RSS"
    assert listings[0].extra["feed_url"] == "https://example.org/feed"


def test_rss_throttled_returns_empty(monkeypatch, db_session):
    db_session.add(
        SearchSource(name="throttled", kind="RSS", category="jobs",
                     url="https://example.org/throttled", enabled=True, cadence="2x")
    )
    db_session.commit()

    monkeypatch.setattr("app.services.sources.rss.feedparser.parse", lambda *a, **k: _EmptyFeed())
    from app.services.sources.rss import RssAdapter

    assert RssAdapter().fetch(db_session, "education") == []
