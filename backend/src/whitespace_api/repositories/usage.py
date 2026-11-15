from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# One statement: insert the first use of the day, or add one while under the limit.
# When the limit is reached the WHERE fails, nothing is returned, and nothing changes.
_CONSUME = text("""
    INSERT INTO usage_counters (user_id, kind, day, count)
    VALUES (:user_id, :kind, :day, 1)
    ON CONFLICT (user_id, kind, day)
    DO UPDATE SET count = usage_counters.count + 1
    WHERE usage_counters.count < :limit
    RETURNING count
""")


async def consume(
    session: AsyncSession, *, user_id: uuid.UUID, kind: str, day: date, limit: int
) -> int | None:
    """Use one unit; the new count, or None if the day's limit is already reached.

    Doesn't commit: the caller commits it together with the work it pays for.
    """
    if limit <= 0:
        return None
    count: int | None = await session.scalar(
        _CONSUME, {"user_id": user_id, "kind": kind, "day": day, "limit": limit}
    )
    return count


async def used(session: AsyncSession, *, user_id: uuid.UUID, kind: str, day: date) -> int:
    count = await session.scalar(
        text("SELECT count FROM usage_counters WHERE user_id = :u AND kind = :k AND day = :d"),
        {"u": user_id, "k": kind, "d": day},
    )
    return int(count or 0)
