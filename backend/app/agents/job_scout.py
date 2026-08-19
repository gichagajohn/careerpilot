"""Agent 1 — JobScout: scheduled discovery of teaching & AI-training opportunities.

Pipeline per run (spec §3, §21, §24, §15):
  sources → adapters → raw listings → normalizer (LLM w/ deterministic fallback)
          → dedup → upsert jobs (+ job_sources) → search_runs audit → cache

The agent is polite: per-source cadence, robots.txt-aware fetching, 24h page
cache, bounded results, and it never touches login-gated platforms directly.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Job, SearchRun, SearchSource
from app.services.dedup import attach_source, find_duplicate, new_cluster_id
from app.services.normalizer import RawListing, normalize_listing
from app.services.relevance import is_relevant
from app.services.sources.registry import ADAPTERS

logger = logging.getLogger("careerpilot.jobscout")

QUERIES_FILE = (
    Path(__file__).resolve().parent.parent / "services" / "sources" / "queries.json"
)

# Minimum hours between runs per source cadence.
# Semantics:
#   "Nx"  → run N times per day (interval = 24/N hours)
#   "daily" → every 20 hours (give a 4h buffer past 24h)
#   "hourly" → every 1 hour
#   anything else → fall back to a safe 12h default
CADENCE_HOURS: dict[str, int] = {
    "3x": 8,      # 3x per day ≈ every 8h (with buffer)
    "2x": 12,     # 2x per day ≈ every 12h
    "1x": 24,     # 1x per day
    "daily": 20,  # legacy alias
    "hourly": 1,
}
DEFAULT_CADENCE_HOURS = 12


def load_queries() -> list[dict]:
    return load_queries_map()["categories"]


def load_queries_map() -> dict:
    with QUERIES_FILE.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _parse_last_run(value: str | None) -> datetime | None:
    """Parse last_run_at into a timezone-aware datetime, or None if missing/invalid."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
    # If naive, assume UTC (DB stores naive datetimes by default in some configs)
    if dt.tzinfo is None:
        from datetime import timezone
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _cadence_hours(cadence: str | None) -> int:
    """Map a cadence string to a minimum number of hours between runs."""
    if not cadence:
        return DEFAULT_CADENCE_HOURS
    key = cadence.lower().strip()
    if key in CADENCE_HOURS:
        return CADENCE_HOURS[key]
    # Try to parse "Nx" pattern
    if key.endswith("x") and key[:-1].isdigit():
        n = int(key[:-1])
        if n > 0:
            return max(1, 24 // n)
    return DEFAULT_CADENCE_HOURS


def _is_due(src: SearchSource) -> bool:
    """Return True if this source should run now.

    Rules:
      - Disabled sources are never due.
      - Sources that have never run are due immediately.
      - Sources with an unparseable last_run_at are treated as "never ran" (due).
      - Otherwise, the source is due if (now - last_run_at) >= cadence hours.
    """
    if not src.enabled:
        return False
    last = _parse_last_run(src.last_run_at)
    if last is None:
        return True
    hours = _cadence_hours(src.cadence)
    elapsed_hours = (datetime.now().astimezone() - last).total_seconds() / 3600
    return elapsed_hours >= hours


def _queries_for(src: SearchSource, queries: list[str] | None) -> list[str]:
    if queries:
        return queries
    all_terms = [c["term"] for c in load_queries()]
    if src.name == "adzuna":
        # stay well within the free-tier quota: core terms, daily cadence
        core = [c["term"] for c in load_queries() if c.get("core")]
        return core or all_terms
    return all_terms


def _upsert(db: Session, listing: RawListing, stats: dict) -> None:
    normalized = normalize_listing(listing, use_llm=True)
    if normalized is None:
        return
    job_in = normalized.job
    dup = find_duplicate(db, job_in.title, job_in.organization_name, job_in.country)
    if dup is not None:
        if attach_source(
            db, dup, normalized.source_name, normalized.source_type, job_in.source_url
        ):
            stats["duplicates"] += 1
        return
    job = Job(
        **job_in.model_dump(),
        status="DISCOVERED",
        verification_status="UNVERIFIED",
        duplicate_group=new_cluster_id(),
    )
    db.add(job)
    db.flush()  # assign job.id for the source link
    attach_source(db, job, normalized.source_name, normalized.source_type, job_in.source_url)
    stats["new_jobs"] += 1


def run_job_scout(
    db: Session,
    source_names: list[str] | None = None,
    queries: list[str] | None = None,
    force: bool = False,
) -> dict:
    settings = get_settings()
    stats = {
        "sources_run": 0,
        "queries_run": 0,
        "listings": 0,
        "filtered_out": 0,
        "new_jobs": 0,
        "duplicates": 0,
        "errors": [],
    }

    sources = db.scalars(
        select(SearchSource).where(
            SearchSource.enabled.is_(True), SearchSource.category == "jobs"
        )
    ).all()

    for src in sources:
        if source_names and src.name not in source_names:
            continue
        adapter_cls = ADAPTERS.get(src.name)
        if adapter_cls is None:
            stats["errors"].append(f"unknown source type: {src.name}")
            continue
        if not force and not _is_due(src):
            continue

        adapter = adapter_cls()
        query_terms = _queries_for(src, queries)
        source_stats = {"listings": 0, "new": 0, "dup": 0}
        for term in query_terms:
            run = SearchRun(source_id=src.id, query=term, started_at=_now_iso())
            try:
                listings = adapter.fetch(db, term)
            except Exception as exc:  # adapter-level failure must not kill the run
                run.finished_at = _now_iso()
                run.error = str(exc)
                stats["errors"].append(f"{src.name}:{term}: {exc}")
                db.add(run)
                db.commit()
                continue

            run.results_found = len(listings)
            for listing in listings:
                stats["listings"] += 1
                source_stats["listings"] += 1
                if settings.jobs_relevance_filter and not is_relevant(listing):
                    stats["filtered_out"] += 1
                    continue
                before_new, before_dup = stats["new_jobs"], stats["duplicates"]
                _upsert(db, listing, stats)
                source_stats["new"] += stats["new_jobs"] - before_new
                source_stats["dup"] += stats["duplicates"] - before_dup

            run.finished_at = _now_iso()
            run.new_opportunities = source_stats["new"]
            db.add(run)
            db.commit()
            stats["queries_run"] += 1

        src.last_run_at = _now_iso()
        db.commit()
        stats["sources_run"] += 1
        logger.info(
            "JobScout %s: %d listings, %d new, %d duplicates",
            src.name,
            source_stats["listings"],
            source_stats["new"],
            source_stats["dup"],
        )

    return stats