from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CHAR, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from whitespace_api.models.base import Base


class MarketBrief(Base):
    """One AI brief per (exporter, product, market), shared by every user who opens it.

    `status` moves pending -> ready | failed. A pending row doubles as a lock, so the
    same brief is never generated twice at once, even across API instances.
    """

    __tablename__ = "market_briefs"

    exporter: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    hs6: Mapped[str] = mapped_column(CHAR(6), primary_key=True)
    market: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    status: Mapped[str] = mapped_column(String(10))
    content: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    usage: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Per-user daily limit counts recent requests.
    __table_args__ = (Index("ix_market_briefs_requested_by_updated", "requested_by", "updated_at"),)
