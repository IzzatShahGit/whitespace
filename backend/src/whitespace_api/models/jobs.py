"""Bookkeeping for scheduled jobs and the emails they send."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from whitespace_api.models.base import Base


class JobLease(Base):
    """Who may run a scheduled job right now. Taken with one conditional UPDATE, held until
    `locked_until` (so a crashed process frees it by itself), and safe behind a connection
    pooler, unlike session advisory locks."""

    __tablename__ = "job_leases"

    name: Mapped[str] = mapped_column(String(40), primary_key=True)
    holder: Mapped[uuid.UUID | None] = mapped_column()
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(300))


class EmailSend(Base):
    """One periodic email to one user (e.g. the digest for ISO week 2026-W47). The row is
    claimed before sending, so reruns and overlapping runs send it once."""

    __tablename__ = "email_sends"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String(20), primary_key=True)
    period: Mapped[str] = mapped_column(String(16), primary_key=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EmailVerification(Base):
    """A one-time link proving the user reads their inbox (needed before we email them
    regularly). Only the token's hash is kept."""

    __tablename__ = "email_verifications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
