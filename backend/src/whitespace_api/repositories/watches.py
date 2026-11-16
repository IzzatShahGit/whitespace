"""Watches: the product-markets users follow.

Every user-facing query is scoped to one user. The two queries at the end read across
users and exist only for the alert job.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection, Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.models.user import User
from whitespace_api.models.watch import Watch


async def list_for_user(session: AsyncSession, user_id: uuid.UUID) -> Sequence[Watch]:
    query = (
        select(Watch).where(Watch.user_id == user_id).order_by(Watch.created_at.desc(), Watch.id)
    )
    return (await session.scalars(query)).all()


async def find(
    session: AsyncSession, *, user_id: uuid.UUID, exporter: str, hs6: str, market: str
) -> Watch | None:
    """This user's watch of the pair, if any."""
    return await session.scalar(
        select(Watch).where(
            Watch.user_id == user_id,
            Watch.exporter == exporter,
            Watch.hs6 == hs6,
            Watch.market == market,
        )
    )


async def add(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    exporter: str,
    hs6: str,
    market: str,
    limit: int,
) -> tuple[Watch, bool] | None:
    """The user's watch of the pair and whether it is new; None if they're at `limit`.

    Locks the user's row first, so concurrent adds by the same user queue up and the
    count can't change between the check and the insert. The lock mode (FOR NO KEY
    UPDATE) blocks no other user, nor inserts elsewhere that reference this one.
    Doesn't commit: the caller's commit releases the lock.
    """
    await session.execute(select(User.id).where(User.id == user_id).with_for_update(key_share=True))
    existing = await find(session, user_id=user_id, exporter=exporter, hs6=hs6, market=market)
    if existing is not None:
        return existing, False
    count = await session.scalar(select(func.count()).where(Watch.user_id == user_id))
    if (count or 0) >= limit:
        return None
    statement = (
        insert(Watch)
        .values(user_id=user_id, exporter=exporter, hs6=hs6, market=market)
        .returning(Watch)
    )
    return (await session.scalars(statement)).one(), True


async def delete_for_user(
    session: AsyncSession, *, user_id: uuid.UUID, watch_id: uuid.UUID
) -> bool:
    result = await session.execute(
        delete(Watch).where(Watch.id == watch_id, Watch.user_id == user_id)
    )
    await session.commit()
    return bool(result.rowcount)  # type: ignore[attr-defined]


# ---------- for the alert job: across users ----------
async def watched_pairs(session: AsyncSession, markets: Collection[str]) -> list[tuple[str, str]]:
    """Distinct (market, hs6) pairs that anyone watches, in `markets` only."""
    query = (
        select(Watch.market, Watch.hs6)
        .where(Watch.market.in_(markets))
        .distinct()
        .order_by(Watch.market, Watch.hs6)
    )
    return [(market, hs6) for market, hs6 in (await session.execute(query)).all()]


async def watching(session: AsyncSession, *, market: str, hs6: str) -> Sequence[Watch]:
    """Every user's watches of this pair."""
    query = select(Watch).where(Watch.market == market, Watch.hs6 == hs6)
    return (await session.scalars(query)).all()
