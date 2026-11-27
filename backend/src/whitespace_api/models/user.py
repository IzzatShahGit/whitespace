from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, String, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from whitespace_api.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)  # stored lowercase
    full_name: Mapped[str] = mapped_column(String(120))
    # None for accounts that only sign in with Google.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    # Google's stable account id ("sub" claim). Emails can change; this can't.
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True)
    # True once someone proved they own the email (today: via Google).
    email_verified: Mapped[bool] = mapped_column(default=False, server_default=false())
    is_active: Mapped[bool] = mapped_column(default=True)
    # The weekly email; only sent once the address is verified.
    digest_enabled: Mapped[bool] = mapped_column(default=False, server_default=false())
    # Interface language (en, ur, bn, ...); None = the browser's choice.
    locale: Mapped[str | None] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # When they typed a password or used Google. Renewed sessions don't change it.
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Any session start or renewal (every 15 minutes of use), so "last seen" is real.
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Demo and test accounts: kept, but shown apart and left out of the real-user numbers.
    is_test: Mapped[bool] = mapped_column(default=False, server_default=false())

    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def has_password(self) -> bool:
        """False for Google-only accounts (they can set a password without a current one)."""
        return self.password_hash is not None


class RefreshToken(Base):
    """One row per signed-in session. Rotated on every refresh, revoked on logout."""

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set when this token was swapped for a new one. Reusing a rotated token means it
    # was copied (theft); reusing one ended by sign-out or a password change doesn't.
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="refresh_tokens")


class UserActivityDay(Base):
    """One row per user per day they used the app (a session started or renewed)."""

    __tablename__ = "user_activity_days"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)

    __table_args__ = (Index("ix_user_activity_days_day", "day"),)


class AdminAction(Base):
    """What an admin changed on an account (disable, enable, sign out, mark as test)."""

    __tablename__ = "admin_actions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    admin_email: Mapped[str] = mapped_column(String(320))
    action: Mapped[str] = mapped_column(String(20))
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    target_email: Mapped[str] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PasswordReset(Base):
    """A one-time link to set a new password, sent by email. Only the token's hash is kept."""

    __tablename__ = "password_resets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
