"""Notifications (the bell). Reads and updates are scoped to one user; `add_many` and
`recipients` are for the alert job."""

from __future__ import annotations

import uuid
from collections.abc import Collection, Sequence
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.models.user import User
from whitespace_api.models.watch import Notification


async def list_for_user(
    session: AsyncSession, *, user_id: uuid.UUID, limit: int
) -> Sequence[Notification]:
    query = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
    )
    return (await session.scalars(query)).all()


async def unread_count(session: AsyncSession, user_id: uuid.UUID) -> int:
    count = await session.scalar(
        select(func.count()).where(Notification.user_id == user_id, Notification.read_at.is_(None))
    )
    return int(count or 0)


async def mark_read(
    session: AsyncSession, *, user_id: uuid.UUID, ids: Collection[uuid.UUID] | None
) -> None:
    """Mark these notifications read, or all of them when `ids` is None.

    Ids that aren't this user's are ignored, so they reveal nothing.
    """
    statement = (
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=func.now())
    )
    if ids is not None:
        statement = statement.where(Notification.id.in_(ids))
    await session.execute(statement)
    await session.commit()


async def add_many(session: AsyncSession, rows: Sequence[dict[str, Any]]) -> Sequence[Notification]:
    """Insert notifications, skipping any whose (user, dedupe_key) already exists.

    One statement, decided by the unique constraint: reruns and concurrent runs can't
    duplicate a notification. Rows go in a fixed order, so two concurrent inserts of the
    same rows queue behind each other instead of deadlocking. Returns only the new ones.
    Doesn't commit.
    """
    if not rows:
        return []
    statement = (
        insert(Notification)
        .values(sorted(rows, key=lambda row: (row["user_id"], row["dedupe_key"])))
        .on_conflict_do_nothing(index_elements=[Notification.user_id, Notification.dedupe_key])
        .returning(Notification)
    )
    return (await session.scalars(statement)).all()


async def recipients(
    session: AsyncSession, user_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """Email addresses of these users, active accounts only."""
    if not user_ids:
        return {}
    query = select(User.id, User.email).where(User.id.in_(user_ids), User.is_active.is_(True))
    return {user_id: email for user_id, email in (await session.execute(query)).all()}  # noqa: C416
