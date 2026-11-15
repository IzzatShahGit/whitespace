from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from whitespace_api.models.base import Base


class ChatThread(Base):
    """One conversation with the Whitespace guide. Only its owner can read or write it."""

    __tablename__ = "chat_threads"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_chat_threads_user_updated", "user_id", "updated_at"),)


class ChatMessage(Base):
    """A user question or a guide reply.

    Replies start `pending` and become `done` or `failed`. A partial unique index allows
    one pending reply per thread, so double-sends can't race, even across API instances.
    """

    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_threads.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(10))  # user | assistant
    status: Mapped[str] = mapped_column(String(10), server_default="done")
    content: Mapped[str] = mapped_column(Text, server_default="")
    cards: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")
    follow_ups: Mapped[list[str]] = mapped_column(JSONB, server_default="[]")
    # Product and market codes the reply was about, so follow-up questions resolve
    # ("tell me about the second one") without resending whole tool outputs.
    memo: Mapped[str | None] = mapped_column(Text)
    grounded: Mapped[bool | None] = mapped_column(Boolean)
    usage: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_chat_messages_thread_created", "thread_id", "created_at"),
        Index(
            "uq_chat_messages_one_pending",
            "thread_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )
