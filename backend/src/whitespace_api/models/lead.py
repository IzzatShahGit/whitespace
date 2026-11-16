from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CHAR, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from whitespace_api.models.base import Base


class TradeLeads(Base):
    """Companies found on the web for one (product, country, side), shared by every user.

    side "buyers": importers and distributors in `country` (for someone selling there).
    side "suppliers": manufacturers and exporters in `country` (for someone buying there).
    Not tied to the user's own country, so one search serves every exporter. `status`
    moves pending -> ready | failed; a pending row is a lock, as for market briefs.
    """

    __tablename__ = "trade_leads"

    hs6: Mapped[str] = mapped_column(CHAR(6), primary_key=True)
    country: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    side: Mapped[str] = mapped_column(String(10), primary_key=True)
    status: Mapped[str] = mapped_column(String(10))
    content: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    usage: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_trade_leads_requested_by_updated", "requested_by", "updated_at"),)
