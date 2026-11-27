from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.models.user import RefreshToken, User, UserActivityDay


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email.lower()))


async def get_user(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def get_user_by_google_sub(session: AsyncSession, google_sub: str) -> User | None:
    return await session.scalar(select(User).where(User.google_sub == google_sub))


async def add_user(
    session: AsyncSession,
    *,
    email: str,
    full_name: str,
    password_hash: str | None = None,
    google_sub: str | None = None,
    email_verified: bool = False,
) -> User:
    user = User(
        email=email.lower(),
        full_name=full_name,
        password_hash=password_hash,
        google_sub=google_sub,
        email_verified=email_verified,
    )
    session.add(user)
    await session.flush()
    return user


async def add_refresh_token(
    session: AsyncSession, *, user_id: uuid.UUID, token_hash: str, expires_at: datetime
) -> None:
    session.add(RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at))
    await session.flush()


async def get_refresh_token(session: AsyncSession, token_hash: str) -> RefreshToken | None:
    return await session.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))


async def mark_seen(session: AsyncSession, user: User, when: datetime) -> None:
    """Remember that this user is using the app now (last seen, and today as an active day)."""
    user.last_seen_at = when
    await session.execute(
        insert(UserActivityDay)
        .values(user_id=user.id, day=when.astimezone(UTC).date())
        .on_conflict_do_nothing()
    )


async def revoke_all_refresh_tokens(
    session: AsyncSession, user_id: uuid.UUID, when: datetime
) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=when)
    )
