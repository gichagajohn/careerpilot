"""CareerPilot AI — FastAPI application entry point.

Run locally:
    uvicorn app.main:app --reload --port 8000

Interactive API docs: http://localhost:8000/docs
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import (
    agents,
    applications,
    auth,
    cover_letters,
    cv,
    dashboard,
    documents,
    jobs,
    notifications,
    profile,
    recommendations,
    scholarships,
)
from app.core.config import get_settings
from app.core.db import SessionLocal, init_db
from app.services.scheduler import start_scheduler, stop_scheduler
from app.services.sources.defaults import bootstrap_sources

logger = logging.getLogger("careerpilot")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    if settings.auto_create_tables:
        init_db()
        logger.info("Tables ensured (auto_create_tables=true)")
    # Discovery sources drive JobScout/ScholarshipScout. Without them the
    # agents silently find nothing, so provision the defaults on first run.
    with SessionLocal() as db:
        bootstrap_sources(db)
    start_scheduler()
    yield
    stop_scheduler()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "CareerPilot AI — personal AI Career & Scholarship agent.\n\n"
            "Phase 1: skeleton, auth, master profile, opportunities, documents, tracker."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api = settings.api_prefix
    app.include_router(auth.router, prefix=api)
    app.include_router(profile.router, prefix=api)
    app.include_router(jobs.router, prefix=api)
    app.include_router(scholarships.router, prefix=api)
    app.include_router(documents.router, prefix=api)
    app.include_router(applications.router, prefix=api)
    app.include_router(dashboard.router, prefix=api)
    app.include_router(agents.router, prefix=api)
    app.include_router(notifications.router, prefix=api)
    app.include_router(recommendations.router, prefix=api)
    app.include_router(cv.router, prefix=api)
    app.include_router(cover_letters.router, prefix=api)

    @app.get("/health", tags=["system"])
    def health() -> dict:
        return {"status": "ok", "app": settings.app_name, "version": "0.1.0"}

    return app


app = create_app()
