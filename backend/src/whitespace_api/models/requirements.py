from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CHAR, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from whitespace_api.models.base import Base


class MarketRequirements(Base):
    """What it takes to ship a product from one country into a market: documents,
    product rules, labels. Researched on the web, shared by every user of that lane.

    `status` moves pending -> ready | failed; a pending row is a lock. `run_id` names the
    run that holds it, so a run that was given up on can't overwrite a newer one.
    """

    __tablename__ = "market_requirements"

    hs6: Mapped[str] = mapped_column(CHAR(6), primary_key=True)
    market: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    exporter: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    status: Mapped[str] = mapped_column(String(10))
    run_id: Mapped[uuid.UUID | None] = mapped_column()
    content: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    usage: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_market_requirements_requested_by_updated", "requested_by", "updated_at"),
    )


class RequirementCheck(Base):
    """One requirement a user has ticked off. A row per item, so ticking two items at
    once can't overwrite each other."""

    __tablename__ = "requirement_checks"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    hs6: Mapped[str] = mapped_column(CHAR(6), primary_key=True)
    market: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    item: Mapped[str] = mapped_column(String(16), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
