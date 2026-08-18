"""Notification routes — in-app inbox + preferences."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import Notification, NotificationPreference, User
from app.schemas.notifications import NotificationOut, NotificationPrefsIn, NotificationPrefsOut
from app.services.notifications import ensure_preferences

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    unread_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Notification]:
    stmt = select(Notification).where(Notification.user_id == current_user.id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    stmt = stmt.order_by(Notification.created_at.desc()).limit(100)
    return list(db.scalars(stmt).all())


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Notification:
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    db.query(Notification).filter(
        Notification.user_id == current_user.id, Notification.is_read.is_(False)
    ).update({"is_read": True})
    db.commit()


@router.get("/preferences", response_model=NotificationPrefsOut)
def get_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationPreference:
    return ensure_preferences(db, current_user.id)


@router.put("/preferences", response_model=NotificationPrefsOut)
def update_preferences(
    payload: NotificationPrefsIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationPreference:
    prefs = ensure_preferences(db, current_user.id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(prefs, field, value)
    db.commit()
    db.refresh(prefs)
    return prefs
