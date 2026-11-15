from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.models.recent import MonthlyTradeCache


async def get_cached(session: AsyncSession, market: str, hs6: str) -> MonthlyTradeCache | None:
    return await session.get(MonthlyTradeCache, (market, hs6))


async def save_cached(
    session: AsyncSession, *, market: str, hs6: str, source: str, payload: dict[str, Any]
) -> MonthlyTradeCache:
    statement = (
        insert(MonthlyTradeCache)
        .values(market=market, hs6=hs6, source=source, payload=payload)
        .on_conflict_do_update(
            index_elements=[MonthlyTradeCache.market, MonthlyTradeCache.hs6],
            set_={"source": source, "payload": payload, "fetched_at": func.now()},
        )
        .returning(MonthlyTradeCache)
        .execution_options(populate_existing=True)
    )
    row = (await session.scalars(statement)).one()
    await session.commit()
    return row
