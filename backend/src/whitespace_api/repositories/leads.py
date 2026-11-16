from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.models.lead import TradeLeads


async def get(session: AsyncSession, hs6: str, country: str, side: str) -> TradeLeads | None:
    return await session.get(TradeLeads, (hs6, country, side), populate_existing=True)


async def claim(
    session: AsyncSession,
    *,
    hs6: str,
    country: str,
    side: str,
    user_id: uuid.UUID,
    abandoned_after: timedelta,
) -> bool:
    """Mark the search pending for this request, unless another request is already on it."""
    values = {"status": "pending", "requested_by": user_id, "error": None}
    statement = (
        insert(TradeLeads)
        .values(hs6=hs6, country=country, side=side, **values)
        .on_conflict_do_update(
            index_elements=[TradeLeads.hs6, TradeLeads.country, TradeLeads.side],
            set_={**values, "updated_at": func.now()},
            where=or_(
                TradeLeads.status != "pending",
                TradeLeads.updated_at < func.now() - abandoned_after,
            ),
        )
        .returning(TradeLeads.hs6)
    )
    claimed = (await session.execute(statement)).first() is not None
    await session.commit()
    return claimed


async def finish(
    session: AsyncSession,
    *,
    hs6: str,
    country: str,
    side: str,
    status: str,
    content: dict[str, Any] | None = None,
    usage: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    await session.execute(
        update(TradeLeads)
        .where(TradeLeads.hs6 == hs6, TradeLeads.country == country, TradeLeads.side == side)
        .values(status=status, content=content, usage=usage, error=error, updated_at=func.now())
    )
    await session.commit()


async def requests_since(session: AsyncSession, user_id: uuid.UUID, since: datetime) -> int:
    query = select(func.count()).where(
        TradeLeads.requested_by == user_id, TradeLeads.updated_at >= since
    )
    return int(await session.scalar(query) or 0)
