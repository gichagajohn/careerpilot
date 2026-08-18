"""Notification service tests — in-app dedup + channel senders."""
from __future__ import annotations

from app.models import Notification, NotificationPreference, User
from app.services.notifications import ensure_preferences, notify


def _user(db_session) -> User:
    from app.core.security import hash_password

    u = User(email="notif@example.com", password_hash=hash_password("StrongPass123"),
             full_name="Test")
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


def test_notify_creates_in_app_row(db_session):
    u = _user(db_session)
    assert notify(db_session, u.id, "HIGH_MATCH", "High match: Math Teacher",
                  "Match 90/100", entity_type="job", entity_id=7) is True
    row = db_session.query(Notification).one()
    assert row.type == "HIGH_MATCH"
    assert row.entity_type == "job" and row.entity_id == 7


def test_notify_deduplicated(db_session):
    u = _user(db_session)
    first = notify(db_session, u.id, "DEADLINE", "Deadline soon", "x",
                   entity_type="scholarship", entity_id=3)
    second = notify(db_session, u.id, "DEADLINE", "Deadline soon", "x",
                    entity_type="scholarship", entity_id=3)
    assert first is True
    assert second is False
    assert db_session.query(Notification).count() == 1


def test_ensure_preferences_creates_default(db_session):
    u = _user(db_session)
    prefs = ensure_preferences(db_session, u.id)
    assert prefs.in_app is True
    assert prefs.email is False
    assert db_session.query(NotificationPreference).count() == 1
    # idempotent
    ensure_preferences(db_session, u.id)
    assert db_session.query(NotificationPreference).count() == 1


def test_email_telegram_fail_quietly(db_session):
    """Without SMTP/Telegram config, notify must not raise."""
    u = _user(db_session)
    assert notify(db_session, u.id, "HIGH_MATCH", "t", "b", entity_type="job", entity_id=1) is True
