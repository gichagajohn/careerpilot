"""Database engine and session management.

SQLite for local development, PostgreSQL in production — same code path,
only the DATABASE_URL changes. PII is encrypted at the application layer
(see core/crypto.py); the database never stores plaintext secrets.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _engine_kwargs(url: str) -> dict:
    kwargs: dict = {"pool_pre_ping": True, "future": True}
    if url.startswith("sqlite"):
        # SQLite doesn't allow the same connection across threads by default
        kwargs["connect_args"] = {"check_same_thread": False}
    return kwargs


engine = create_engine(get_settings().database_url, **_engine_kwargs(get_settings().database_url))

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yield a scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables (dev convenience). Use Alembic in production."""
    from app import models  # noqa: F401  (registers all models on Base)

    Base.metadata.create_all(bind=engine)
    _ensure_dev_columns()


# Columns added in later phases — keep an existing dev SQLite DB in sync
# without a full migration (production uses Alembic instead).
_DEV_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "jobs": [("match_details", "JSON")],
    "scholarships": [("match_details", "JSON"), ("priority_score", "FLOAT")],
    "notifications": [("entity_type", "VARCHAR(40)"), ("entity_id", "INTEGER")],
}


def _ensure_dev_columns() -> None:
    if not get_settings().is_sqlite:
        return
    from sqlalchemy import inspect

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    with engine.begin() as conn:
        for table, columns in _DEV_COLUMNS.items():
            if table not in tables:
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, col_type in columns:
                if name not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {col_type}")
    engine.dispose()  # refresh inspector cache
