"""Exchange rates (ExchangeRate-API open access: free, no key, updated daily).

Rates are against the US dollar and cached in-process for 12 hours, so the service is
called at most twice a day per API instance. Attribution is shown wherever rates are.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import httpx

RATES_URL = "https://open.er-api.com/v6/latest/USD"
SOURCE = "ExchangeRate-API"
CACHE_SECONDS = 12 * 3600
TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class FxError(RuntimeError):
    pass


@dataclass(frozen=True)
class Rates:
    per_usd: dict[str, float]  # units of each currency per 1 USD
    updated: str  # as published, e.g. "Sun, 15 Nov 2026 00:02:32 +0000"
    fetched_at: float


_cache: Rates | None = None
_refresh = asyncio.Lock()  # concurrent requests share one refresh instead of each calling out


async def rates(client: httpx.AsyncClient, now: float | None = None) -> Rates:
    """Current rates, from cache when fresh. Serves a stale copy if the service is down."""
    now = time.time() if now is None else now
    if (cached := _fresh(now)) is not None:
        return cached
    async with _refresh:
        if (cached := _fresh(now)) is not None:  # another request refreshed while we waited
            return cached
        return await _fetch(client, now)


def _fresh(now: float) -> Rates | None:
    return _cache if _cache is not None and now - _cache.fetched_at < CACHE_SECONDS else None


async def _fetch(client: httpx.AsyncClient, now: float) -> Rates:
    global _cache
    try:
        response = await client.get(RATES_URL, timeout=TIMEOUT)
        response.raise_for_status()
        body = response.json()
        if body.get("result") != "success":
            raise FxError("Rates service returned an error")
        _cache = Rates(
            per_usd={k: float(v) for k, v in body["rates"].items()},
            updated=str(body.get("time_last_update_utc", "")),
            fetched_at=now,
        )
    except (httpx.HTTPError, ValueError, KeyError, FxError) as exc:
        if _cache is not None:
            return _cache  # yesterday's rate beats no rate
        raise FxError(f"Exchange rates unavailable: {type(exc).__name__}") from exc
    return _cache
