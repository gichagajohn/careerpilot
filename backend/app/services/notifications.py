"""Notifications service — in-app (always) + email (SMTP) + Telegram (bot).

Never raises: a channel failure is logged, never allowed to break a run.
Notification preferences live in notification_preferences (default: in-app on,
email/telegram off until the user enables them and provides credentials).
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Notification, NotificationPreference, User

logger = logging.getLogger("careerpilot.notifications")


def ensure_preferences(db: Session, user_id: int) -> NotificationPreference:
    prefs = db.get(NotificationPreference, user_id)
    if prefs is None:
        prefs = NotificationPreference(user_id=user_id)
        db.add(prefs)
        db.commit()
    return prefs


def _existing(db: Session, user_id: int, ntype: str, entity_type: str | None,
              entity_id: int | None) -> bool:
    if entity_type is None:
        return False
    row = db.scalar(
        select(Notification.id).where(
            Notification.user_id == user_id,
            Notification.type == ntype,
            Notification.entity_type == entity_type,
            Notification.entity_id == entity_id,
        ).limit(1)
    )
    return row is not None


def notify(db: Session, user_id: int, ntype: str, title: str, body: str,
           entity_type: str | None = None, entity_id: int | None = None) -> bool:
    """Create a notification (deduplicated per entity+type) and push to channels."""
    if _existing(db, user_id, ntype, entity_type, entity_id):
        return False

    settings = get_settings()
    prefs = ensure_preferences(db, user_id)

    notification = Notification(
        user_id=user_id,
        type=ntype,
        title=title[:255],
        body=body,
        channel="IN_APP",
        entity_type=entity_type,
        entity_id=entity_id,
    )
    db.add(notification)

    # Email
    if prefs.email and settings.smtp_host:
        user = db.get(User, user_id)
        if user and user.email:
            try:
                _send_email(user.email, title, body)
                notification.sent_at = __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds")
            except Exception:
                logger.exception("Email notification failed for %s", user.email)

    # Telegram
    if prefs.telegram and settings.telegram_bot_token and settings.telegram_chat_id:
        try:
            _send_telegram(settings.telegram_bot_token, settings.telegram_chat_id, f"{title}\n\n{body}")
            notification.sent_at = __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds")
        except Exception:
            logger.exception("Telegram notification failed")

    db.commit()
    return True


def _send_email(to: str, subject: str, body: str) -> None:
    settings = get_settings()
    msg = EmailMessage()
    msg["Subject"] = f"[CareerPilot] {subject}"
    msg["From"] = settings.email_from or settings.smtp_user
    msg["To"] = to
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)


def _send_telegram(token: str, chat_id: str, text: str) -> None:
    resp = httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text[:4000]},
        timeout=20,
    )
    resp.raise_for_status()


def notify_high_match(db: Session, user_id: int, entity_type: str, entity_id: int,
                      title: str, score: float) -> bool:
    body = (
        f"Match score: {score:.0f}/100.\n"
        f"Open {entity_type}: {title}\n"
        "Review it in the dashboard and prepare an application when ready."
    )
    return notify(db, user_id, "HIGH_MATCH", f"High match: {title[:80]}", body,
                  entity_type=entity_type, entity_id=entity_id)


def notify_deadline(db: Session, user_id: int, entity_type: str, entity_id: int,
                    title: str, deadline: str) -> bool:
    body = f"Deadline {deadline} is approaching for: {title}"
    return notify(db, user_id, "DEADLINE", f"Deadline approaching: {title[:80]}", body,
                  entity_type=entity_type, entity_id=entity_id)
