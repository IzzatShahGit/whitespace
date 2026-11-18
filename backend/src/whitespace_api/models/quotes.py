"""Quotes and proforma invoices, and the seller details printed on them."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CHAR, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from whitespace_api.models.base import Base


class BusinessDetails(Base):
    """The user's company as it appears on quotes. `next_quote` numbers quotes: taken with
    one UPDATE ... RETURNING, so two quotes made at once never share a number."""

    __tablename__ = "business_details"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    company_name: Mapped[str | None] = mapped_column(String(160))
    address: Mapped[str | None] = mapped_column(String(400))
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(320))
    website: Mapped[str | None] = mapped_column(String(255))
    tax_id: Mapped[str | None] = mapped_column(String(60))
    bank_details: Mapped[str | None] = mapped_column(Text)
    # Registered Exporter number (EU/UK/Swiss/Norwegian/Turkish GSP origin statements).
    rex_number: Mapped[str | None] = mapped_column(String(40))
    next_quote: Mapped[int] = mapped_column(Integer, server_default="1")
    next_invoice: Mapped[int] = mapped_column(Integer, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Quote(Base):
    """A saved quote or proforma. `content` is a full snapshot (seller, buyer, prices,
    freight), so later edits to business details or rates never change an issued quote."""

    __tablename__ = "quotes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    number: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(10))  # quote | proforma
    hs6: Mapped[str] = mapped_column(CHAR(6))
    market: Mapped[str] = mapped_column(CHAR(3))
    buyer_name: Mapped[str] = mapped_column(String(160))
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pipeline_contacts.id", ondelete="SET NULL")
    )
    total_usd: Mapped[float] = mapped_column(Numeric(14, 2))
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_quotes_user_created", "user_id", "created_at"),)
