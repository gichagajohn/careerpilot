"""Which master profile should an agent score against?

Agents (matcher, CV tailor, cover-letter writer) historically did:

    select(MasterProfile).where(MasterProfile.is_active.is_(True))
                         .order_by(MasterProfile.id).limit(1)

i.e. "the first active profile in the table" — not "this user's profile".
That is wrong in two ways:

  1. With more than one account, agents would score opportunities and write
     documents against whoever registered first.
  2. Now that every user gets an empty master profile at registration, the
     first row in the table may be an *empty* placeholder, which would produce
     meaningless match scores and unusable CVs.

This module resolves the profile explicitly, and refuses to silently fall back
to a different user's data.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MasterProfile


def profile_is_populated(profile: MasterProfile | None) -> bool:
    """True once there is enough real content for an agent to work from.

    This is deliberately looser than the ``profile_complete`` flag the UI uses
    to decide whether to show onboarding. An agent only needs *some* verified
    substance to score against; the UI wants the headline fields filled in.

    What it must exclude is the empty placeholder created at registration,
    which carries only the account's name and email — scoring against that
    would produce meaningless match scores.
    """
    if profile is None:
        return False
    if not (profile.full_name or "").strip():
        return False
    return bool(
        (profile.profession or "").strip()
        or (profile.summary or "").strip()
        or profile.education
        or profile.experience
        or profile.skills
    )


def profile_for_user(db: Session, user_id: int) -> MasterProfile | None:
    """Return this user's own master profile (active row preferred)."""
    return db.scalar(
        select(MasterProfile)
        .where(MasterProfile.user_id == user_id)
        .order_by(MasterProfile.is_active.desc(), MasterProfile.id.asc())
        .limit(1)
    )


def active_profile_for(db: Session, user_id: int | None) -> MasterProfile | None:
    """Resolve the profile an agent should use.

    - With a ``user_id``: that user's profile, and only theirs. If it is empty
      we return None rather than borrowing someone else's data.
    - Without one (the scheduler has no request context): the first *populated*
      active profile, deterministically by id. This keeps the single-user
      personal deployment working while never picking an empty placeholder.
    """
    if user_id is not None:
        profile = profile_for_user(db, user_id)
        return profile if profile_is_populated(profile) else None

    candidates = db.scalars(
        select(MasterProfile)
        .where(MasterProfile.is_active.is_(True))
        .order_by(MasterProfile.id.asc())
    ).all()
    for profile in candidates:
        if profile_is_populated(profile):
            return profile
    return None
