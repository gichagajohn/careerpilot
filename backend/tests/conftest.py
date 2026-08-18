"""Test configuration — isolated SQLite database per test run.

Environment variables are set BEFORE importing app modules so config picks
them up. An .env file in backend/ would otherwise override these (pydantic
gives priority to actual environment variables over .env file values).
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet

# Isolated test database
_TEST_DB = Path(__file__).parent / "test_app.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ["SECRET_KEY"] = secrets.token_urlsafe(48)
os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()  # valid key for this run
os.environ["AUTO_CREATE_TABLES"] = "true"
os.environ["CORS_ORIGINS"] = '["http://localhost:3000"]'
os.environ["ENABLE_SCHEDULER"] = "false"  # tests run the pipeline manually

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_headers(client):
    """Register a user and return Authorization headers + user info."""
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "john@example.com", "password": "StrongPass123", "full_name": "John Gichaga"},
    )
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
