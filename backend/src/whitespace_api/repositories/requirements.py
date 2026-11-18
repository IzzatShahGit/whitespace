from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.models.requirements import MarketRequirements, RequirementCheck

Key = tuple[str, str, str]  # (hs6, market, exporter)


async def get(session: AsyncSession, key: Key) -> MarketRequirements | None:
    return await session.get(MarketRequirements, key, populate_existing=True)


async def claim(
    session: AsyncSession, key: Key, *, user_id: uuid.UUID, abandoned_after: timedelta
) -> uuid.UUID | None:
    """Take the research lock for this lane, atomically. Returns the run's id, or None
    when another run holds it (and isn't abandoned)."""
    hs6, market, exporter = key
    run_id = uuid.uuid4()
    values = {"status": "pending", "run_id": run_id, "requested_by": user_id, "error": None}
    statement = (
        insert(MarketRequirements)
        .values(hs6=hs6, market=market, exporter=exporter, **values)
        .on_conflict_do_update(
            index_elements=[
                MarketRequirements.hs6,
                MarketRequirements.market,
                MarketRequirements.exporter,
            ],
            set_={**values, "updated_at": func.now()},
            where=or_(
                MarketRequirements.status != "pending",
                MarketRequirements.updated_at < func.now() - abandoned_after,
            ),
        )
        .returning(MarketRequirements.run_id)
    )
    claimed = (await session.execute(statement)).scalar_one_or_none()
    await session.commit()
    return claimed


async def finish(
    session: AsyncSession,
    key: Key,
    run_id: uuid.UUID,
    *,
    status: str,
    content: dict[str, Any] | None = None,
    usage: dict[str, Any] | None = None,
    error: str | None = None,
    keep_content: bool = False,
) -> bool:
    """Store a run's result, only if it still holds the lock (a newer run may have taken
    over an abandoned one). A failed refresh keeps the previous good content."""
    hs6, market, exporter = key
    values: dict[str, Any] = {
        "status": status,
        "usage": usage,
        "error": error,
        "updated_at": func.now(),
    }
    if not keep_content:
        values["content"] = content
    result = await session.execute(
        update(MarketRequirements)
        .where(
            MarketRequirements.hs6 == hs6,
            MarketRequirements.market == market,
            MarketRequirements.exporter == exporter,
            MarketRequirements.run_id == run_id,
        )
        .values(**values)
        .returning(MarketRequirements.hs6)
    )
    await session.commit()
    return result.first() is not None


async def requests_since(session: AsyncSession, user_id: uuid.UUID, since: datetime) -> int:
    query = select(func.count()).where(
        MarketRequirements.requested_by == user_id, MarketRequirements.updated_at >= since
    )
    return int(await session.scalar(query) or 0)


# --- a user's ticks ---


async def done(session: AsyncSession, user_id: uuid.UUID, hs6: str, market: str) -> list[str]:
    rows = await session.scalars(
        select(RequirementCheck.item).where(
            RequirementCheck.user_id == user_id,
            RequirementCheck.hs6 == hs6,
            RequirementCheck.market == market,
        )
    )
    return sorted(rows)


async def set_done(
    session: AsyncSession, user_id: uuid.UUID, hs6: str, market: str, item: str, value: bool
) -> None:
    """Idempotent: ticking twice or unticking an unticked item is fine."""
    if value:
        await session.execute(
            insert(RequirementCheck)
            .values(user_id=user_id, hs6=hs6, market=market, item=item)
            .on_conflict_do_nothing()
        )
    else:
        await session.execute(
            delete(RequirementCheck).where(
                RequirementCheck.user_id == user_id,
                RequirementCheck.hs6 == hs6,
                RequirementCheck.market == market,
                RequirementCheck.item == item,
            )
        )
    await session.commit()
