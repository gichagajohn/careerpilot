"""Default discovery sources + first-run provisioning.

`search_sources` rows drive the whole discovery pipeline: JobScout and
ScholarshipScout iterate over them, so an empty table means the agents run,
find nothing, and report success — a silent no-op that leaves the dashboard
permanently empty.

These defaults used to live only in scripts/seed.py, which meant any
deployment where the seed script was never run had no sources at all. They now
live in the application and are provisioned on startup, so a fresh database
becomes productive without a manual step. scripts/seed.py imports from here so
there is a single source of truth.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import SearchSource

logger = logging.getLogger("careerpilot.sources")

# Cadence is per-source:
#   3x    = three times a day (every scheduled run)
#   2x    = twice a day
#   daily = once a day (used for quota-limited APIs like Adzuna)
DEFAULT_JOB_SOURCES: list[dict] = [
    {"name": "adzuna", "kind": "API", "url": "https://api.adzuna.com/v1/api/jobs", "category": "jobs", "cadence": "daily",
     "notes": "Official Adzuna API (free tier). Needs ADZUNA_APP_ID/KEY. Core queries only."},
    {"name": "remotive", "kind": "API", "url": "https://remotive.com/api/remote-jobs", "category": "jobs", "cadence": "3x",
     "notes": "Remote jobs API (free, no key)."},
    {"name": "remoteok", "kind": "API", "url": "https://remoteok.com/api", "category": "jobs", "cadence": "3x",
     "notes": "Remote tech jobs API (free, no key)."},
    {"name": "arbeitnow", "kind": "API", "url": "https://www.arbeitnow.com/api/job-board-api", "category": "jobs", "cadence": "3x",
     "notes": "Europe-leaning job feed (free, no key)."},
    {"name": "websearch", "kind": "SEARCH", "url": None, "category": "jobs", "cadence": "2x",
     "notes": "Web search (Google CSE / Serper / Tavily) — discovery only, no scraping of banned sites."},
    {"name": "rss", "kind": "RSS", "url": "https://reliefweb.int/jobs/rss.xml?search%5Bvalue%5D%5B0%5D=education", "category": "jobs", "cadence": "2x",
     "notes": "ReliefWeb education jobs feed. Add more feeds (UN, schools) in the UI/DB."},
]

DEFAULT_SCHOLARSHIP_SOURCES: list[dict] = [
    {"name": "websearch", "kind": "SEARCH", "url": None, "category": "scholarships", "cadence": "daily",
     "notes": "Web search for Master's scholarships (fully funded / Kenya / Africa variants)."},
    {"name": "rss", "kind": "RSS", "url": "https://opportunitiesforyouth.org/feed/", "category": "scholarships", "cadence": "daily",
     "notes": "Opportunities for Youth feed (scholarships + opportunities for Africans)."},
    {"name": "scholarship_pages", "kind": "FETCH", "url": None, "category": "scholarships", "cadence": "daily",
     "notes": "Official programme pages (DAAD, Erasmus+, Chevening, Commonwealth, Mastercard, AIMS...). "
              "FULLY FUNDED is only accepted with explicit official evidence (spec §4)."},
    {"name": "scholarship_daad", "kind": "FETCH", "url": "https://www.daad.de/en/study-and-research-in-germany/scholarships/", "category": "scholarships", "cadence": "daily",
     "notes": "DAAD official scholarships page."},
    {"name": "scholarship_erasmus_mundus", "kind": "FETCH", "url": "https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en", "category": "scholarships", "cadence": "daily",
     "notes": "Erasmus Mundus catalogue (fully funded joint Master's)."},
    {"name": "scholarship_chevening", "kind": "FETCH", "url": "https://www.chevening.org/scholarships/", "category": "scholarships", "cadence": "daily",
     "notes": "Chevening Scholarships (UK government)."},
    {"name": "scholarship_commonwealth", "kind": "FETCH", "url": "https://cscuk.fcdo.gov.uk/scholarships/", "category": "scholarships", "cadence": "daily",
     "notes": "Commonwealth Scholarship Commission (UK)."},
    {"name": "scholarship_mastercard", "kind": "FETCH", "url": "https://mastercardfdn.org/all/scholarships/", "category": "scholarships", "cadence": "daily",
     "notes": "Mastercard Foundation Scholars Program."},
    {"name": "scholarship_aims", "kind": "FETCH", "url": "https://nexteinstein.org/", "category": "scholarships", "cadence": "daily",
     "notes": "AIMS Next Einstein (African math sciences MSc)."},
    {"name": "scholarship_mandela_rhodes", "kind": "FETCH", "url": "https://mandelarhodes.org/", "category": "scholarships", "cadence": "daily",
     "notes": "Mandela Rhodes Scholarships."},
    {"name": "scholarship_fulbright", "kind": "FETCH", "url": "https://foreign.fulbrightonline.org/", "category": "scholarships", "cadence": "daily",
     "notes": "Fulbright Foreign Student Program."},
    {"name": "scholarship_gates_cambridge", "kind": "FETCH", "url": "https://www.gatescambridge.org/", "category": "scholarships", "cadence": "daily",
     "notes": "Gates Cambridge Scholarships."},
]

ALL_DEFAULT_SOURCES = DEFAULT_JOB_SOURCES + DEFAULT_SCHOLARSHIP_SOURCES


def ensure_default_sources(db: Session) -> int:
    """Insert any missing default source. Idempotent; returns the number added.

    Existing rows are never modified — if the user disabled a source or edited
    its URL, that choice is preserved.
    """
    added = 0
    for row in ALL_DEFAULT_SOURCES:
        exists = db.scalar(
            select(SearchSource).where(
                SearchSource.name == row["name"],
                SearchSource.category == row["category"],
            )
        )
        if exists is None:
            db.add(SearchSource(**row))
            added += 1
    if added:
        db.commit()
    return added


def bootstrap_sources(db: Session) -> int:
    """Startup hook: provision default sources, never fatally."""
    try:
        added = ensure_default_sources(db)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Could not provision default discovery sources")
        return 0
    if added:
        logger.info("Provisioned %d default discovery sources", added)
    return added
