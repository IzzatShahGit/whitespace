"""Sanctions lists (official, refreshed daily) and the buyer checks made against them."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from whitespace_api.models.base import Base


class SanctionSource(Base):
    """One official list and how fresh our copy is. `checksum` (of the files as
    downloaded) lets a refresh skip a list that hasn't changed."""

    __tablename__ = "sanction_sources"

    source: Mapped[str] = mapped_column(String(8), primary_key=True)  # ofac | un | eu | uk
    loaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checksum: Mapped[str | None] = mapped_column(String(64))
    parties: Mapped[int] = mapped_column(Integer, server_default="0")
    names: Mapped[int] = mapped_column(Integer, server_default="0")
    error: Mapped[str | None] = mapped_column(String(300))


class SanctionName(Base):
    """One name (primary or alias) of a listed party. `name_core` is the comparable
    form (core_name) and carries a trigram index for fuzzy search."""

    __tablename__ = "sanction_names"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(8))
    ref: Mapped[str] = mapped_column(String(40))  # the list's own id for the party
    kind: Mapped[str] = mapped_column(String(10))  # entity | individual
    name: Mapped[str] = mapped_column(String(400))
    name_core: Mapped[str] = mapped_column(String(400))
    program: Mapped[str | None] = mapped_column(String(300))
    url: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index(
            "ix_sanction_names_core_trgm",
            "name_core",
            postgresql_using="gin",
            postgresql_ops={"name_core": "gin_trgm_ops"},
        ),
        Index("ix_sanction_names_source", "source"),
    )


class BuyerCheck(Base):
    """The latest check of a pipeline contact: verdict for the card, full result on open."""

    __tablename__ = "buyer_checks"

    contact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pipeline_contacts.id", ondelete="CASCADE"), primary_key=True
    )
    verdict: Mapped[str] = mapped_column(String(5))  # green | amber | red
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
