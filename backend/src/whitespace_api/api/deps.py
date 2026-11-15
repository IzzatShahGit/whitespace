"""Shared route dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.core.config import Settings, get_settings
from whitespace_api.core.db import get_session
from whitespace_api.models.user import User
from whitespace_api.services import auth as auth_service

DbSession = Annotated[AsyncSession, Depends(get_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]


async def get_current_user(
    db: DbSession,
    settings: AppSettings,
    ws_access: Annotated[str | None, Cookie()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Signed-in user from the access cookie (browser) or a Bearer header (API clients)."""
    token = ws_access
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:]
    user = await auth_service.user_from_access_token(db, token, settings)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
