"""Recent movement: monthly customs data newer than the annual rankings.

Fetched on demand per (market, product) and cached, so only markets people actually
open are ever requested. These numbers are shown beside the ranking, never mixed into
the score (the score uses one consistent annual source for every market).
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.core.config import Settings
from whitespace_api.integrations import monthly_trade as source
from whitespace_api.repositories import monthly as repo
from whitespace_api.schemas.trade import MonthPoint, RecentMovement, RecentSupplier

log = logging.getLogger(__name__)

SOURCE_NAMES = {"eurostat": "Eurostat (EU customs)", "census": "US Census Bureau"}
# Why shares can differ from the annual ranking (which traces goods to where they
# were made): EU statistics credit goods arriving via another member to that member.
SOURCE_NOTES = {
    "eurostat": (
        "EU figures count goods that arrive through another EU country (such as the "
        "Netherlands) as imports from that country, so shares can be lower than in the "
        "annual data, which traces goods to where they were made."
    ),
    "census": None,
}
HISTORY_MONTHS = 36  # enough for two full 12-month windows despite publication lag
WINDOW = 12
TOP_SUPPLIERS = 5


class NotCoveredError(Exception):
    """No monthly source for this market. The message is safe to show."""


class UnavailableError(Exception):
    """The source can't be reached and nothing is cached. The message is safe to show."""


@lru_cache
def http_client() -> httpx.AsyncClient:
    """One pooled client per process (closed on shutdown in main.py)."""
    return httpx.AsyncClient(headers={"User-Agent": "whitespace-api"})


def _since(today: date) -> date:
    month = today.year * 12 + today.month - 1 - (HISTORY_MONTHS - 1)
    return date(month // 12, month % 12 + 1, 1)


def summarise(
    payload: dict[str, Any],
    *,
    exporter_code: str | None,
    fetched_at: datetime,
    stale: bool,
) -> RecentMovement:
    """Two 12-month windows from the cached monthly data. Pure: no I/O."""
    total: dict[str, float] = payload["total"]
    partners: dict[str, Any] = payload["partners"]
    months = sorted(m for m, v in total.items() if v > 0)
    if not months:
        raise UnavailableError("No monthly imports recorded for this product yet")

    recent, before = months[-WINDOW:], months[-2 * WINDOW : -WINDOW]
    has_before = len(before) == WINDOW
    exporter_values: dict[str, float] = (
        partners.get(exporter_code, {}).get("values", {}) if exporter_code else {}
    )

    def window_sum(values: dict[str, float], window: list[str]) -> float:
        return sum(values.get(m, 0.0) for m in window)

    recent_total = window_sum(total, recent)
    before_total = window_sum(total, before) if has_before else 0.0

    def share(values: dict[str, float], window: list[str], denominator: float) -> float:
        return min(window_sum(values, window) / denominator, 1.0) if denominator else 0.0

    ranked = sorted(partners.values(), key=lambda p: window_sum(p["values"], recent), reverse=True)[
        :TOP_SUPPLIERS
    ]
    return RecentMovement(
        source=SOURCE_NAMES[payload["source"]],
        currency=payload["currency"],
        latest_month=months[-1],
        months=[
            MonthPoint(month=m, total=total[m], exporter=exporter_values.get(m, 0.0))
            for m in months[-2 * WINDOW :]
        ],
        change_12m=(recent_total / before_total - 1) if before_total else None,
        exporter_share_recent=share(exporter_values, recent, recent_total),
        exporter_share_before=share(exporter_values, before, before_total) if has_before else None,
        suppliers=[
            RecentSupplier(
                name=p["name"],
                share_recent=share(p["values"], recent, recent_total),
                share_before=share(p["values"], before, before_total) if has_before else None,
            )
            for p in ranked
            if window_sum(p["values"], recent) > 0
        ],
        note=SOURCE_NOTES[payload["source"]],
        fetched_at=fetched_at,
        stale=stale,
    )


async def _fetch(
    source_name: str, market: str, hs6: str, settings: Settings
) -> source.MonthlyImports:
    since = _since(datetime.now(UTC).date())
    client = http_client()
    if source_name == "eurostat":
        return await source.fetch_eurostat(client, market, hs6, since)
    if settings.census_api_key is None:
        raise UnavailableError("US monthly data isn't configured")
    return await source.fetch_census(client, hs6, since, settings.census_api_key.get_secret_value())


async def recent_movement(
    db: AsyncSession, *, market: str, hs6: str, exporter: str, settings: Settings
) -> RecentMovement:
    source_name = source.source_for(market)
    if source_name is None:
        raise NotCoveredError("Monthly data covers EU countries and the United States")

    cached = await repo.get_cached(db, market, hs6)
    fresh_after = datetime.now(UTC) - timedelta(days=settings.monthly_cache_days)
    stale = False
    if cached is None or cached.fetched_at < fresh_after:
        try:
            payload = await _fetch(source_name, market, hs6, settings)
            cached = await repo.save_cached(
                db, market=market, hs6=hs6, source=source_name, payload=dict(payload)
            )
        except source.SourceError as exc:
            log.warning("Monthly data refresh failed for %s/%s: %s", market, hs6, exc)
            if cached is None:
                raise UnavailableError("The monthly data source isn't responding") from exc
            stale = True  # serve the older copy, labelled

    return summarise(
        cached.payload,
        exporter_code=source.EXPORTER_CODES.get(exporter, {}).get(source_name),
        fetched_at=cached.fetched_at,
        stale=stale,
    )
