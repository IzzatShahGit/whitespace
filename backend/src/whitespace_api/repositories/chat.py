from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.models.chat import ChatMessage, ChatThread


async def create_thread(session: AsyncSession, *, user_id: uuid.UUID, title: str) -> ChatThread:
    thread = ChatThread(user_id=user_id, title=title)
    session.add(thread)
    await session.flush()
    return thread


async def get_thread(
    session: AsyncSession, *, user_id: uuid.UUID, thread_id: uuid.UUID
) -> ChatThread | None:
    """The thread, only if this user owns it."""
    return await session.scalar(
        select(ChatThread).where(ChatThread.id == thread_id, ChatThread.user_id == user_id)
    )


async def list_threads(
    session: AsyncSession, *, user_id: uuid.UUID, limit: int
) -> Sequence[ChatThread]:
    query = (
        select(ChatThread)
        .where(ChatThread.user_id == user_id)
        .order_by(ChatThread.updated_at.desc())
        .limit(limit)
    )
    return (await session.scalars(query)).all()


async def delete_thread(session: AsyncSession, *, user_id: uuid.UUID, thread_id: uuid.UUID) -> bool:
    result = await session.execute(
        delete(ChatThread).where(ChatThread.id == thread_id, ChatThread.user_id == user_id)
    )
    await session.commit()
    return bool(result.rowcount)  # type: ignore[attr-defined]


async def messages(session: AsyncSession, thread_id: uuid.UUID) -> Sequence[ChatMessage]:
    query = (
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.created_at, ChatMessage.role.desc())  # user before its reply
    )
    return (await session.scalars(query)).all()


async def history(
    session: AsyncSession, *, thread_id: uuid.UUID, before: uuid.UUID, limit: int
) -> list[ChatMessage]:
    """The last finished messages before `before`, oldest first (context for a reply)."""
    pending = select(ChatMessage.created_at).where(ChatMessage.id == before).scalar_subquery()
    query = (
        select(ChatMessage)
        .where(
            ChatMessage.thread_id == thread_id,
            ChatMessage.status == "done",
            ChatMessage.created_at < pending,
        )
        .order_by(ChatMessage.created_at.desc(), ChatMessage.role)
        .limit(limit)
    )
    return list(reversed((await session.scalars(query)).all()))


async def expire_pending(
    session: AsyncSession, *, thread_id: uuid.UUID, older_than: timedelta
) -> None:
    """Fail replies a crashed process left pending, so they don't block the thread forever."""
    await session.execute(
        update(ChatMessage)
        .where(
            ChatMessage.thread_id == thread_id,
            ChatMessage.status == "pending",
            ChatMessage.created_at < func.now() - older_than,
        )
        .values(status="failed", content="This reply was interrupted. Please ask again.")
    )


async def add_turn(
    session: AsyncSession, *, thread_id: uuid.UUID, text: str
) -> tuple[ChatMessage, ChatMessage]:
    """The question and a pending reply. Raises IntegrityError if a reply is already pending."""
    question = ChatMessage(thread_id=thread_id, role="user", status="done", content=text)
    session.add(question)
    await session.flush()  # the question is created first, so it sorts first
    reply = ChatMessage(thread_id=thread_id, role="assistant", status="pending")
    session.add(reply)
    await session.flush()
    return question, reply


async def finish(session: AsyncSession, *, message_id: uuid.UUID, **values: Any) -> None:
    """Store a reply's outcome and bump its thread. A deleted thread is fine (no rows)."""
    thread_id = await session.scalar(
        update(ChatMessage)
        .where(ChatMessage.id == message_id, ChatMessage.status == "pending")
        .values(**values)
        .returning(ChatMessage.thread_id)
    )
    if thread_id is not None:
        await session.execute(
            update(ChatThread).where(ChatThread.id == thread_id).values(updated_at=func.now())
        )
    await session.commit()
