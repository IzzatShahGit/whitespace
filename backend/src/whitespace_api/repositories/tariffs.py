from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.models.tariff import TariffCache


async def get_cached(session: AsyncSession, reporter: str, hs6: str) -> TariffCache | None:
    return await session.get(TariffCache, (reporter, hs6))


async def save_cached(
    session: AsyncSession, *, reporter: str, hs6: str, source: str, payload: dict[str, Any]
) -> TariffCache:
    statement = (
        insert(TariffCache)
        .values(reporter=reporter, hs6=hs6, source=source, payload=payload)
        .on_conflict_do_update(
            index_elements=[TariffCache.reporter, TariffCache.hs6],
            set_={"source": source, "payload": payload, "fetched_at": func.now()},
        )
        .returning(TariffCache)
        .execution_options(populate_existing=True)
    )
    row = (await session.scalars(statement)).one()
    await session.commit()
    return row
