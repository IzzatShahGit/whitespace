"""A user's outreach pipeline: companies they're contacting, and what happened."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CHAR,
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from whitespace_api.models.base import Base


class PipelineContact(Base):
    """One company a user is working on, for one product and market.

    `version` goes up on every change: an edit sent with an older version is refused,
    so two tabs (or two devices) can't silently overwrite each other.
    `name_key` (normalised name) is unique per (user, product, market): saving the same
    company twice, even at the same moment, keeps one row.
    """

    __tablename__ = "pipeline_contacts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    hs6: Mapped[str] = mapped_column(CHAR(6))
    market: Mapped[str] = mapped_column(CHAR(3))
    side: Mapped[str] = mapped_column(String(10), server_default="buyers")
    name: Mapped[str] = mapped_column(String(160))
    name_key: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str | None] = mapped_column(String(20))
    city: Mapped[str | None] = mapped_column(String(80))
    website: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(Text)
    stage: Mapped[str] = mapped_column(String(12), server_default="to_contact")
    note: Mapped[str | None] = mapped_column(Text)
    follow_up_on: Mapped[date | None] = mapped_column(Date)
    last_contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "hs6", "market", "name_key", name="uq_pipeline_contact"),
        Index("ix_pipeline_contacts_user_updated", "user_id", "updated_at"),
        Index("ix_pipeline_contacts_follow_up", "follow_up_on"),
    )


class PipelineEvent(Base):
    """What happened to a contact: added, moved stage, note, follow-up date."""

    __tablename__ = "pipeline_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    contact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pipeline_contacts.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(20))
    detail: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_pipeline_events_contact_created", "contact_id", "created_at"),)
