"""Sign-up, sign-in, session refresh and sign-out."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.core import security
from whitespace_api.core.config import Settings
from whitespace_api.models.user import User
from whitespace_api.repositories import users as repo
from whitespace_api.services.google_oauth import GoogleIdentity


class AuthError(Exception):
    """Bad credentials or an invalid session. The message is safe to show users."""


class EmailTakenError(AuthError):
    pass


@dataclass(frozen=True)
class Session:
    user: User
    access_token: str
    refresh_token: str


async def _start_session(db: AsyncSession, user: User, settings: Settings) -> Session:
    refresh = security.new_refresh_token()
    await repo.add_refresh_token(
        db,
        user_id=user.id,
        token_hash=security.hash_token(refresh),
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
    )
    return Session(
        user=user,
        access_token=security.create_access_token(user.id, settings),
        refresh_token=refresh,
    )


async def register(
    db: AsyncSession, *, email: str, password: str, full_name: str, settings: Settings
) -> Session:
    if await repo.get_user_by_email(db, email):
        raise EmailTakenError("An account with this email already exists")
    try:
        user = await repo.add_user(
            db,
            email=email,
            full_name=full_name.strip(),
            password_hash=security.hash_password(password),
        )
    except IntegrityError as exc:  # two sign-ups with the same email at once
        await db.rollback()
        raise EmailTakenError("An account with this email already exists") from exc
    session = await _start_session(db, user, settings)
    await db.commit()
    return session


async def login(db: AsyncSession, *, email: str, password: str, settings: Settings) -> Session:
    user = await repo.get_user_by_email(db, email)
    valid = security.verify_password(password, user.password_hash if user else None)
    if not user or not valid or not user.is_active:
        raise AuthError("Incorrect email or password")
    user.last_login_at = datetime.now(UTC)
    session = await _start_session(db, user, settings)
    await db.commit()
    return session


async def sign_in_with_google(
    db: AsyncSession, identity: GoogleIdentity, settings: Settings
) -> Session:
    """Sign in, link, or create an account from a verified Google identity.

    1. Known Google account          -> sign in.
    2. Email matches existing account -> link Google to it. If that account's email
       was never verified, its password may belong to someone who registered the
       email first (account pre-hijacking), so the password is removed and all of
       its sessions end. The owner can set a new password later via reset.
    3. Otherwise                      -> create a Google-only account.
    """
    now = datetime.now(UTC)
    user = await repo.get_user_by_google_sub(db, identity.sub)
    if user is None:
        user = await repo.get_user_by_email(db, identity.email)
        if user is not None:
            if not user.email_verified:
                user.password_hash = None
                await repo.revoke_all_refresh_tokens(db, user.id, now)
            user.google_sub = identity.sub
            user.email_verified = True
        else:
            try:
                user = await repo.add_user(
                    db,
                    email=identity.email,
                    full_name=identity.name,
                    google_sub=identity.sub,
                    email_verified=True,
                )
            except IntegrityError as exc:  # same account created concurrently
                await db.rollback()
                raise AuthError("Please try signing in again") from exc
    if not user.is_active:
        raise AuthError("This account is disabled")
    user.last_login_at = now
    session = await _start_session(db, user, settings)
    await db.commit()
    return session


async def refresh(db: AsyncSession, *, refresh_token: str, settings: Settings) -> Session:
    """Swap a refresh token for a new pair. The old token stops working."""
    now = datetime.now(UTC)
    stored = await repo.get_refresh_token(db, security.hash_token(refresh_token))
    if stored is None or stored.expires_at <= now:
        raise AuthError("Session expired, please sign in again")
    if stored.rotated_at is not None:
        # A token that was already swapped was used again: it was copied. End every session.
        await repo.revoke_all_refresh_tokens(db, stored.user_id, now)
        await db.commit()
        raise AuthError("Session expired, please sign in again")
    if stored.revoked_at is not None:  # signed out, or ended by a password change
        raise AuthError("Session expired, please sign in again")
    user = await repo.get_user(db, stored.user_id)
    if user is None or not user.is_active:
        raise AuthError("Session expired, please sign in again")
    stored.revoked_at = stored.rotated_at = now
    session = await _start_session(db, user, settings)
    await db.commit()
    return session


async def logout(db: AsyncSession, *, refresh_token: str | None) -> None:
    if not refresh_token:
        return
    stored = await repo.get_refresh_token(db, security.hash_token(refresh_token))
    if stored and stored.revoked_at is None:
        stored.revoked_at = datetime.now(UTC)
        await db.commit()


async def user_from_access_token(
    db: AsyncSession, token: str | None, settings: Settings
) -> User | None:
    if not token:
        return None
    user_id: uuid.UUID | None = security.decode_access_token(token, settings)
    if user_id is None:
        return None
    user = await repo.get_user(db, user_id)
    return user if user and user.is_active else None


# ---------- account ----------
def _check_password(user: User, password: str | None) -> None:
    """Accounts with a password must confirm it; Google-only accounts have none to give."""
    if user.password_hash is not None and not security.verify_password(
        password or "", user.password_hash
    ):
        raise AuthError("Your current password is incorrect")


async def update_name(db: AsyncSession, user: User, *, full_name: str) -> User:
    user.full_name = full_name.strip()
    await db.commit()
    return user


async def change_password(
    db: AsyncSession,
    user: User,
    *,
    current_password: str | None,
    new_password: str,
    settings: Settings,
) -> Session:
    """Set a new password, sign out every other session, and start a fresh one here."""
    _check_password(user, current_password)
    user.password_hash = security.hash_password(new_password)
    await repo.revoke_all_refresh_tokens(db, user.id, datetime.now(UTC))
    session = await _start_session(db, user, settings)
    await db.commit()
    return session


async def delete_account(db: AsyncSession, user: User, *, password: str | None) -> None:
    """Delete the user and everything that belongs to them (cascades in the database)."""
    _check_password(user, password)
    await db.delete(user)
    await db.commit()
