"""Shipments: the paperwork for one won deal, built from an issued quote."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CHAR, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from whitespace_api.models.base import Base


class Shipment(Base):
    """One shipment per quote (unique), so pressing "prepare documents" twice opens the
    same one. `content` holds the quote snapshot plus the shipping details the user
    fills in; `version` guards edits like the pipeline's."""

    __tablename__ = "shipments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    quote_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("quotes.id", ondelete="SET NULL"), unique=True
    )
    invoice_number: Mapped[str] = mapped_column(String(20))
    hs6: Mapped[str] = mapped_column(CHAR(6))
    market: Mapped[str] = mapped_column(CHAR(3))
    buyer_name: Mapped[str] = mapped_column(String(160))
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_shipments_user_created", "user_id", "created_at"),)
