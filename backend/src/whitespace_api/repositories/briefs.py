from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.models.brief import MarketBrief


async def get(session: AsyncSession, exporter: str, hs6: str, market: str) -> MarketBrief | None:
    return await session.get(MarketBrief, (exporter, hs6, market), populate_existing=True)


async def claim(
    session: AsyncSession,
    *,
    exporter: str,
    hs6: str,
    market: str,
    user_id: uuid.UUID,
    abandoned_after: timedelta,
) -> bool:
    """Mark the brief pending for this request, unless another request is already on it.

    One atomic statement: a new row is inserted, or an existing one is taken over only if
    it isn't pending (or its job looks abandoned). True if this request got the job.
    """
    values = {"status": "pending", "requested_by": user_id, "error": None}
    statement = (
        insert(MarketBrief)
        .values(exporter=exporter, hs6=hs6, market=market, **values)
        .on_conflict_do_update(
            index_elements=[MarketBrief.exporter, MarketBrief.hs6, MarketBrief.market],
            set_={**values, "updated_at": func.now()},
            where=or_(
                MarketBrief.status != "pending",
                MarketBrief.updated_at < func.now() - abandoned_after,
            ),
        )
        .returning(MarketBrief.exporter)
    )
    claimed = (await session.execute(statement)).first() is not None
    await session.commit()
    return claimed


async def finish(
    session: AsyncSession,
    *,
    exporter: str,
    hs6: str,
    market: str,
    status: str,
    content: dict[str, Any] | None = None,
    usage: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    await session.execute(
        update(MarketBrief)
        .where(
            MarketBrief.exporter == exporter,
            MarketBrief.hs6 == hs6,
            MarketBrief.market == market,
        )
        .values(status=status, content=content, usage=usage, error=error, updated_at=func.now())
    )
    await session.commit()


async def requests_since(session: AsyncSession, user_id: uuid.UUID, since: datetime) -> int:
    query = select(func.count()).where(
        MarketBrief.requested_by == user_id, MarketBrief.updated_at >= since
    )
    return int(await session.scalar(query) or 0)
