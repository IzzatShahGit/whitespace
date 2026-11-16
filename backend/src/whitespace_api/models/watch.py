from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CHAR, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from whitespace_api.models.base import Base


class Watch(Base):
    """A product and market a user follows for one exporter country, e.g. towels from
    Pakistan into Germany. The alert job checks every watched pair against fresh
    monthly customs data.

    Codes have no foreign keys to the trade tables, which the pipeline reloads (see
    UserProfile); they are validated when the watch is created. The unique constraint
    makes watching the same pair twice a no-op, even under concurrent requests.
    """

    __tablename__ = "watches"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    exporter: Mapped[str] = mapped_column(CHAR(3))
    hs6: Mapped[str] = mapped_column(CHAR(6))
    market: Mapped[str] = mapped_column(CHAR(3))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        # Also serves "this user's watches": user_id leads the index.
        UniqueConstraint("user_id", "exporter", "hs6", "market", name="uq_watches_user_pair"),
        # The alert job walks watches by pair, across users.
        Index("ix_watches_market_hs6", "market", "hs6"),
    )


class Notification(Base):
    """An in-app message for one user (the bell), written by the alert job.

    `dedupe_key` names the fact being reported (kind, pair and data month) and is unique
    per user, so rerunning the job, or two runs at once, can never repeat a message.
    """

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(300))  # in-app path, e.g. /app/markets/...
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    dedupe_key: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("user_id", "dedupe_key", name="uq_notifications_user_dedupe"),
        Index("ix_notifications_user_created", "user_id", text("created_at DESC")),
        # The unread count runs on every page load (the bell): index only unread rows.
        Index("ix_notifications_user_unread", "user_id", postgresql_where=text("read_at IS NULL")),
    )
