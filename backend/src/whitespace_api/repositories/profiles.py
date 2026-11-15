from __future__ import annotations

import uuid

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.models.profile import UserProfile


async def get_profile(session: AsyncSession, user_id: uuid.UUID) -> UserProfile | None:
    return await session.get(UserProfile, user_id)


async def upsert_profile(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    exporter: str,
    role: str,
    goal: str,
    products: list[str],
    current_markets: list[str],
) -> UserProfile:
    """Create or replace in one statement (no read-then-write race)."""
    values = {
        "exporter": exporter,
        "role": role,
        "goal": goal,
        "products": products,
        "current_markets": current_markets,
    }
    statement = (
        insert(UserProfile)
        .values(user_id=user_id, **values)
        .on_conflict_do_update(
            index_elements=[UserProfile.user_id], set_={**values, "updated_at": func.now()}
        )
        .returning(UserProfile)
        .execution_options(populate_existing=True)
    )
    profile = (await session.scalars(statement)).one()
    await session.commit()
    return profile
