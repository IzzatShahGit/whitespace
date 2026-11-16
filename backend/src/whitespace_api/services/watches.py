"""Watchlists: follow a product in a market for one exporter country, and read the
notifications the alert job writes about it. Everything is scoped to the signed-in user.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.core.config import Settings
from whitespace_api.models.user import User
from whitespace_api.models.watch import Watch
from whitespace_api.repositories import notifications as notification_repo
from whitespace_api.repositories import profiles as profile_repo
from whitespace_api.repositories import trade as trade_repo
from whitespace_api.repositories import watches as repo
from whitespace_api.schemas.trade import CountryOut, ProductOut
from whitespace_api.schemas.watch import (
    MarkReadIn,
    NotificationOut,
    NotificationsPage,
    UnreadCount,
    WatchIn,
    WatchOut,
    WatchStatus,
)
from whitespace_api.services.alerts import monthly_markets


class WatchNotFoundError(Exception):
    """No such watch for this user. Safe to show."""


class InvalidWatchError(Exception):
    """The pair can't be watched: unknown codes, or not a ranked market. Safe to show."""


class WatchLimitError(Exception):
    """The user already watches as many pairs as allowed. Safe to show."""


async def _to_out(db: AsyncSession, watches: Sequence[Watch], settings: Settings) -> list[WatchOut]:
    """Attach names in two queries. Codes gone from a later data release show as codes."""
    codes = sorted({code for w in watches for code in (w.exporter, w.market)})
    countries = await trade_repo.countries_by_code(db, codes)
    products = await trade_repo.products_by_code(db, sorted({w.hs6 for w in watches}))
    covered = monthly_markets(settings)

    def country(code: str) -> CountryOut:
        found = countries.get(code)
        return CountryOut(code=code, name=found.name if found else code)

    def product(hs6: str) -> ProductOut:
        found = products.get(hs6)
        return ProductOut(hs6=hs6, description=found.description if found else f"Product {hs6}")

    return [
        WatchOut(
            id=w.id,
            exporter=country(w.exporter),
            product=product(w.hs6),
            market=country(w.market),
            alerts_available=w.market in covered,
            created_at=w.created_at,
        )
        for w in watches
    ]


async def _exporter(db: AsyncSession, user: User, requested: str | None) -> str | None:
    """The exporter asked for, else the user's own country (None without a profile)."""
    if requested is not None:
        return requested
    profile = await profile_repo.get_profile(db, user.id)
    return profile.exporter if profile else None


async def list_watches(db: AsyncSession, user: User, settings: Settings) -> list[WatchOut]:
    return await _to_out(db, await repo.list_for_user(db, user.id), settings)


async def add_watch(
    db: AsyncSession, user: User, body: WatchIn, settings: Settings
) -> tuple[WatchOut, bool]:
    """Watch a ranked market; also returns whether the watch is new.

    Watching a pair twice returns the existing watch, even at the limit.
    """
    exporter = await _exporter(db, user, body.exporter)
    if exporter is None:
        raise InvalidWatchError("Choose the exporter country, or set yours in your profile")
    ranked = await trade_repo.get_opportunity(
        db, exporter=exporter, hs6=body.hs6, market=body.market
    )
    if ranked is None:
        raise InvalidWatchError(
            f"{body.market} isn't a ranked market for product {body.hs6} from {exporter}"
        )
    added = await repo.add(
        db,
        user_id=user.id,
        exporter=exporter,
        hs6=body.hs6,
        market=body.market,
        limit=settings.watch_limit,
    )
    if added is None:
        await db.rollback()
        raise WatchLimitError(
            f"You're already watching {settings.watch_limit} markets, the most allowed. "
            "Stop watching one to add another."
        )
    watch, created = added
    await db.commit()
    return (await _to_out(db, [watch], settings))[0], created


async def watch_status(
    db: AsyncSession, user: User, *, exporter: str | None, hs6: str, market: str
) -> WatchStatus:
    exporter = await _exporter(db, user, exporter)
    watch = (
        await repo.find(db, user_id=user.id, exporter=exporter, hs6=hs6, market=market)
        if exporter
        else None
    )
    return WatchStatus(watching=watch is not None, id=watch.id if watch else None)


async def delete_watch(db: AsyncSession, user: User, watch_id: uuid.UUID) -> None:
    if not await repo.delete_for_user(db, user_id=user.id, watch_id=watch_id):
        raise WatchNotFoundError("Watch not found")


# ---------- notifications ----------
async def list_notifications(db: AsyncSession, user: User, *, limit: int) -> NotificationsPage:
    rows = await notification_repo.list_for_user(db, user_id=user.id, limit=limit)
    return NotificationsPage(
        unread=await notification_repo.unread_count(db, user.id),
        items=[NotificationOut.model_validate(n, from_attributes=True) for n in rows],
    )


async def mark_read(db: AsyncSession, user: User, body: MarkReadIn) -> UnreadCount:
    await notification_repo.mark_read(db, user_id=user.id, ids=None if body.all else body.ids)
    return UnreadCount(unread=await notification_repo.unread_count(db, user.id))
