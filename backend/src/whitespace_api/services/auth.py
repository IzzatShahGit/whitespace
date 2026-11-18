"""Sign-up, sign-in, session refresh and sign-out."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.core import security, tasks
from whitespace_api.core.config import Settings
from whitespace_api.models.user import PasswordReset, User
from whitespace_api.notify.email import EmailMessage, Sender, get_sender
from whitespace_api.repositories import users as repo
from whitespace_api.services.google_oauth import GoogleIdentity

log = logging.getLogger(__name__)
RESETS_PER_HOUR = 3  # links one account can be sent an hour


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


# ---------- password reset ----------
def _reset_email(user: User, link: str, minutes: int) -> EmailMessage:
    name = user.full_name.split()[0] if user.full_name.strip() else "there"
    return EmailMessage(
        to=user.email,
        subject="Reset your Whitespace password",
        text=(
            f"Hi {name},\n\n"
            "Someone (hopefully you) asked to reset the password for your Whitespace "
            f"account. Open this link to choose a new one:\n\n{link}\n\n"
            f"The link works once, for {minutes} minutes. If you didn't ask for it, "
            "ignore this email: your password stays the same.\n\n"
            "Whitespace\n"
        ),
    )


async def _deliver(sender: Sender, message: EmailMessage) -> None:
    try:
        await sender.send(message)
    except Exception as exc:  # never surface delivery errors to the caller
        log.warning("Password reset email failed: %s", type(exc).__name__)


async def request_password_reset(
    db: AsyncSession, *, email: str, settings: Settings, sender: Sender | None = None
) -> None:
    """Email a one-time reset link if the account exists. Says nothing either way, and
    sends in the background, so the response can't reveal who has an account."""
    user = await repo.get_user_by_email(db, email)
    if user is None or not user.is_active:
        return
    now = datetime.now(UTC)
    recent = await db.scalar(
        select(func.count())
        .select_from(PasswordReset)
        .where(
            PasswordReset.user_id == user.id,
            PasswordReset.created_at > now - timedelta(hours=1),
        )
    )
    if (recent or 0) >= RESETS_PER_HOUR:
        return
    token = security.new_refresh_token()
    db.add(
        PasswordReset(
            user_id=user.id,
            token_hash=security.hash_token(token),
            expires_at=now + timedelta(minutes=settings.reset_token_minutes),
        )
    )
    await db.commit()
    link = f"{settings.public_app_url.rstrip('/')}/reset-password?token={token}"
    message = _reset_email(user, link, settings.reset_token_minutes)
    tasks.spawn(_deliver(sender or get_sender(settings), message))


async def reset_password(
    db: AsyncSession, *, token: str, new_password: str, settings: Settings
) -> Session:
    """Use a reset link: set the password, end every session, sign in here."""
    now = datetime.now(UTC)
    reset = await db.scalar(
        select(PasswordReset).where(PasswordReset.token_hash == security.hash_token(token))
    )
    if reset is None or reset.used_at is not None or reset.expires_at <= now:
        raise AuthError("This reset link has expired or was already used. Ask for a new one.")
    user = await repo.get_user(db, reset.user_id)
    if user is None or not user.is_active:
        raise AuthError("This reset link has expired or was already used. Ask for a new one.")
    # Every open link for this account stops working too.
    await db.execute(
        update(PasswordReset)
        .where(PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None))
        .values(used_at=now)
    )
    user.password_hash = security.hash_password(new_password)
    user.email_verified = True  # they just proved they read this inbox
    user.last_login_at = now
    await repo.revoke_all_refresh_tokens(db, user.id, now)
    session = await _start_session(db, user, settings)
    await db.commit()
    return session


async def delete_account(db: AsyncSession, user: User, *, password: str | None) -> None:
    """Delete the user and everything that belongs to them (cascades in the database)."""
    _check_password(user, password)
    await db.delete(user)
    await db.commit()
