"""The signed-in user's profile and personal dashboard."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from whitespace_api.api.deps import CurrentUser, DbSession
from whitespace_api.schemas.profile import Dashboard, ProfileIn, ProfileOut
from whitespace_api.services import profile as profile_service

router = APIRouter(prefix="/me", tags=["profile"])

_NO_PROFILE = HTTPException(status.HTTP_404_NOT_FOUND, "Profile not set up yet")


@router.get("/profile", response_model=ProfileOut)
async def get_profile(user: CurrentUser, db: DbSession) -> ProfileOut:
    try:
        return await profile_service.get_profile(db, user)
    except profile_service.NoProfileError as exc:
        raise _NO_PROFILE from exc


@router.put("/profile", response_model=ProfileOut)
async def save_profile(body: ProfileIn, user: CurrentUser, db: DbSession) -> ProfileOut:
    """Create or replace the profile (onboarding and "edit preferences" both use this)."""
    try:
        return await profile_service.save_profile(db, user, body)
    except profile_service.InvalidProfileError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


@router.get("/dashboard", response_model=Dashboard)
async def dashboard(user: CurrentUser, db: DbSession) -> Dashboard:
    """The best new markets for each of the user's products."""
    try:
        return await profile_service.dashboard(db, user)
    except profile_service.NoProfileError as exc:
        raise _NO_PROFILE from exc
