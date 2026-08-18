"""Agent 2 — ScholarshipScout: scheduled discovery of Master's opportunities.

Mirrors JobScout (Phase 2) for scholarships (spec §4). Collects the full
19-field record and enforces the "fully funded only on official evidence"
rule inside the normalizer. Discovery is deliberately 1–2 runs per day.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.job_scout import _is_due, _now_iso, load_queries_map
from app.core.config import get_settings
from app.models import Scholarship, SearchRun, SearchSource
from app.services.dedup import attach_scholarship_source, find_duplicate_scholarship, new_cluster_id
from app.services.normalizer import RawListing, normalize_scholarship_listing
from app.services.relevance import is_relevant_scholarship
from app.services.sources.registry import ADAPTERS
from app.services.sources.scholarship_pages import ScholarshipPagesAdapter

logger = logging.getLogger("careerpilot.scholarshipscout")


def _scholarship_queries() -> list[str]:
    """Base terms + funding/eligibility modifiers (kept modest: 2×/day max)."""
    base = [c["term"] for c in load_queries_map().get("scholarship_categories", [])]
    variants: list[str] = []
    for term in base:
        variants.append(term)
        variants.append(f"{term} fully funded")
        variants.append(f"{term} scholarship")
    return variants


def _queries_for(src: SearchSource) -> list[str]:
    if src.kind == "FETCH":
        return []  # URL-driven: the adapter ignores queries
    return _scholarship_queries()


def _upsert(db: Session, listing: RawListing, stats: dict) -> None:
    normalized = normalize_scholarship_listing(listing, use_llm=True)
    if normalized is None:
        return
    sch_in = normalized.scholarship
    dup = find_duplicate_scholarship(db, sch_in.name, sch_in.university)
    if dup is not None:
        if attach_scholarship_source(db, dup, normalized.source_name,
                                     normalized.source_type, sch_in.official_url):
            stats["duplicates"] += 1
        return
    sch = Scholarship(
        **sch_in.model_dump(),
        status="DISCOVERED",
        verification_status="UNVERIFIED",
        duplicate_group=new_cluster_id(),
    )
    db.add(sch)
    db.flush()
    attach_scholarship_source(db, sch, normalized.source_name,
                              normalized.source_type, sch_in.official_url)
    stats["new_scholarships"] += 1


def run_scholarship_scout(
    db: Session,
    source_names: list[str] | None = None,
    force: bool = False,
) -> dict:
    settings = get_settings()
    stats = {
        "sources_run": 0,
        "queries_run": 0,
        "listings": 0,
        "filtered_out": 0,
        "new_scholarships": 0,
        "duplicates": 0,
        "errors": [],
    }

    sources = db.scalars(
        select(SearchSource).where(
            SearchSource.enabled.is_(True), SearchSource.category == "scholarships"
        )
    ).all()

    for src in sources:
        if source_names and src.name not in source_names:
            continue
        adapter_cls = ADAPTERS.get(src.name)
        if adapter_cls is None and src.kind == "FETCH":
            adapter_cls = ScholarshipPagesAdapter  # per-program official pages
        if adapter_cls is None:
            stats["errors"].append(f"unknown source type: {src.name}")
            continue
        if not force and not _is_due(src):
            continue

        adapter = adapter_cls()
        query_terms = _queries_for(src)
        source_stats = {"listings": 0, "new": 0, "dup": 0}

        if query_terms:
            for term in query_terms:
                run = SearchRun(source_id=src.id, query=term, started_at=_now_iso())
                try:
                    listings = adapter.fetch(db, term)
                except Exception as exc:
                    run.finished_at = _now_iso()
                    run.error = str(exc)
                    stats["errors"].append(f"{src.name}:{term}: {exc}")
                    db.add(run)
                    db.commit()
                    continue
                _process(db, listings, run, stats, source_stats)
                stats["queries_run"] += 1
        else:
            # URL-driven source (scholarship_pages): one run, no query
            run = SearchRun(source_id=src.id, query="<official pages>", started_at=_now_iso())
            try:
                listings = adapter.fetch(db, None)
            except Exception as exc:
                run.finished_at = _now_iso()
                run.error = str(exc)
                stats["errors"].append(f"{src.name}: {exc}")
                db.add(run)
                db.commit()
                continue
            _process(db, listings, run, stats, source_stats)

        src.last_run_at = _now_iso()
        db.commit()
        stats["sources_run"] += 1
        logger.info(
            "ScholarshipScout %s: %d listings, %d new, %d duplicates",
            src.name, source_stats["listings"], source_stats["new"], source_stats["dup"],
        )

    return stats


def _process(db: Session, listings: list[RawListing], run: SearchRun,
             stats: dict, source_stats: dict) -> None:
    settings = get_settings()
    run.results_found = len(listings)
    for listing in listings:
        stats["listings"] += 1
        source_stats["listings"] += 1
        if settings.scholarship_relevance_filter and not is_relevant_scholarship(listing):
            stats["filtered_out"] += 1
            continue
        before_new, before_dup = stats["new_scholarships"], stats["duplicates"]
        _upsert(db, listing, stats)
        source_stats["new"] += stats["new_scholarships"] - before_new
        source_stats["dup"] += stats["duplicates"] - before_dup
    run.finished_at = _now_iso()
    run.new_opportunities = source_stats["new"]
    db.add(run)
    db.commit()
