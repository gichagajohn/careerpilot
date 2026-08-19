"""Master profile routes — the single source of truth for all generated documents.

Only the authenticated owner can read/write. Phone is encrypted at rest and
decrypted only for the owner in the API response.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.crypto import decrypt_text, encrypt_text
from app.core.db import get_db
from app.models import Certification, Education, Experience, MasterProfile, Skill, User
from app.schemas.profile import (
    CertificationIn,
    CertificationOut,
    EducationIn,
    EducationOut,
    ExperienceIn,
    ExperienceOut,
    MasterProfileIn,
    MasterProfileOut,
    SkillIn,
    SkillOut,
)

logger = logging.getLogger("careerpilot.profile")

router = APIRouter(prefix="/profile", tags=["profile"])


def ensure_master_profile(db: Session, user: User) -> MasterProfile:
    """Return this user's master profile, creating an empty one on first use.

    The profile is *always* keyed on the authenticated ``user.id`` — never on
    email — so a profile can only ever be reached by its owner.

    A first-time user (registered but never having saved a profile) previously
    got a 404 here, which deadlocked the dashboard: the only caller of
    PUT /profile is the Profile page's edit form, and that form was never
    rendered because the page bailed out on the 404. We now create an empty
    placeholder row instead, and the UI shows the setup form for it.
    """
    profile = _select_profile(db, user)
    if profile is not None:
        # Self-heal a row that was left inactive: GET filtered on is_active
        # while PUT did not, so an inactive row was invisible yet updatable.
        if not profile.is_active:
            profile.is_active = True
            db.commit()
            db.refresh(profile)
        return profile

    profile = MasterProfile(
        user_id=user.id,
        full_name=user.full_name or "",
        email=user.email,
        is_active=True,
    )
    db.add(profile)
    try:
        db.commit()
    except IntegrityError:
        # Another concurrent request created it first — reuse that row.
        db.rollback()
        profile = _select_profile(db, user)
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not create the master profile. Please retry.",
            ) from None
        return profile
    db.refresh(profile)
    return profile


def _select_profile(db: Session, user: User) -> MasterProfile | None:
    """Owner-scoped lookup: active profile first, then any older/inactive row."""
    return db.scalar(
        select(MasterProfile)
        .where(MasterProfile.user_id == user.id)
        .order_by(MasterProfile.is_active.desc(), MasterProfile.id.asc())
        .limit(1)
    )


def _active_profile(db: Session, user: User) -> MasterProfile:
    """Back-compat alias — sub-resources use the same get-or-create path."""
    return ensure_master_profile(db, user)


def _profile_is_complete(profile: MasterProfile) -> bool:
    """A profile is 'complete' once the user has supplied the minimum facts."""
    return bool((profile.full_name or "").strip() and (profile.profession or "").strip())


def _to_out(profile: MasterProfile) -> MasterProfileOut:
    out = MasterProfileOut.model_validate(profile)
    out.phone = decrypt_text(profile.phone_encrypted)
    out.profile_complete = _profile_is_complete(profile)
    return out


# ── Master profile ──────────────────────────────────────────────


@router.get("", response_model=MasterProfileOut)
def get_profile(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> MasterProfileOut:
    """Return the authenticated user's master profile.

    First-time users get an empty profile (``profile_complete: false``) rather
    than a 404, so the dashboard can render the setup form immediately.
    """
    profile = ensure_master_profile(db, current_user)
    return _to_out(profile)


@router.put("", response_model=MasterProfileOut)
def upsert_profile(
    payload: MasterProfileIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MasterProfileOut:
    profile = ensure_master_profile(db, current_user)

    data = payload.model_dump(exclude_unset=True)
    if "phone" in data:
        data["phone_encrypted"] = encrypt_text(data.pop("phone"))
    for field, value in data.items():
        setattr(profile, field, value)
    if not profile.full_name:
        profile.full_name = current_user.full_name or ""
    profile.is_active = True
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Failed to save master profile for user_id=%s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save the master profile. Please try again.",
        ) from None
    db.refresh(profile)
    return _to_out(profile)


# ── Education ───────────────────────────────────────────────────


@router.post("/education", response_model=EducationOut, status_code=status.HTTP_201_CREATED)
def add_education(
    payload: EducationIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EducationOut:
    item = Education(profile_id=_active_profile(db, current_user).id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return EducationOut.model_validate(item)


@router.put("/education/{item_id}", response_model=EducationOut)
def update_education(
    item_id: int,
    payload: EducationIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EducationOut:
    profile = _active_profile(db, current_user)
    item = db.get(Education, item_id)
    if item is None or item.profile_id != profile.id:
        raise HTTPException(status_code=404, detail="Education entry not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return EducationOut.model_validate(item)


@router.delete("/education/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_education(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    profile = _active_profile(db, current_user)
    item = db.get(Education, item_id)
    if item is None or item.profile_id != profile.id:
        raise HTTPException(status_code=404, detail="Education entry not found")
    db.delete(item)
    db.commit()


# ── Experience ──────────────────────────────────────────────────


@router.post("/experience", response_model=ExperienceOut, status_code=status.HTTP_201_CREATED)
def add_experience(
    payload: ExperienceIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExperienceOut:
    item = Experience(profile_id=_active_profile(db, current_user).id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return ExperienceOut.model_validate(item)


@router.put("/experience/{item_id}", response_model=ExperienceOut)
def update_experience(
    item_id: int,
    payload: ExperienceIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExperienceOut:
    profile = _active_profile(db, current_user)
    item = db.get(Experience, item_id)
    if item is None or item.profile_id != profile.id:
        raise HTTPException(status_code=404, detail="Experience entry not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return ExperienceOut.model_validate(item)


@router.delete("/experience/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_experience(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    profile = _active_profile(db, current_user)
    item = db.get(Experience, item_id)
    if item is None or item.profile_id != profile.id:
        raise HTTPException(status_code=404, detail="Experience entry not found")
    db.delete(item)
    db.commit()


# ── Skills ──────────────────────────────────────────────────────


@router.post("/skills", response_model=SkillOut, status_code=status.HTTP_201_CREATED)
def add_skill(
    payload: SkillIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SkillOut:
    profile = _active_profile(db, current_user)
    existing = db.scalar(
        select(Skill).where(
            Skill.profile_id == profile.id,
            Skill.name.ilike(payload.name.strip()),
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Skill already exists")
    item = Skill(
        profile_id=profile.id,
        name=payload.name.strip(),
        category=payload.category,
        level=payload.level,
        approved=True,
        source="USER APPROVED",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return SkillOut.model_validate(item)


@router.delete("/skills/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_skill(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    profile = _active_profile(db, current_user)
    item = db.get(Skill, item_id)
    if item is None or item.profile_id != profile.id:
        raise HTTPException(status_code=404, detail="Skill not found")
    db.delete(item)
    db.commit()


# ── Certifications ──────────────────────────────────────────────


@router.post(
    "/certifications", response_model=CertificationOut, status_code=status.HTTP_201_CREATED
)
def add_certification(
    payload: CertificationIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CertificationOut:
    item = Certification(
        profile_id=_active_profile(db, current_user).id, **payload.model_dump()
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return CertificationOut.model_validate(item)


@router.delete("/certifications/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_certification(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    profile = _active_profile(db, current_user)
    item = db.get(Certification, item_id)
    if item is None or item.profile_id != profile.id:
        raise HTTPException(status_code=404, detail="Certification not found")
    db.delete(item)
    db.commit()
