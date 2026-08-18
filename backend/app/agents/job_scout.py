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

QUERIES_FILE = Path(__file__).resolve().parent.parent / "services" / "sources" / "queries.json"

# Minimum hours between runs per source cadence
CADENCE_HOURS = {"3x": 7, "2x": 11, "daily": 20, "hourly": 1}


def load_queries() -> list[dict]:
    return load_queries_map()["categories"]


def load_queries_map() -> dict:
    with QUERIES_FILE.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _is_due(src: SearchSource) -> bool:
    if not src.last_run_at:
        return True
    try:
        last = datetime.fromisoformat(src.last_run_at)
    except ValueError:
        return True
    hours = CADENCE_HOURS.get((src.cadence or "3x").lower(), 7)
    elapsed = (datetime.now().astimezone() - last).total_seconds() / 3600
    return elapsed >= hours


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
        if attach_source(db, dup, normalized.source_name, normalized.source_type, job_in.source_url):
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
            src.name, source_stats["listings"], source_stats["new"], source_stats["dup"],
        )

    return stats
