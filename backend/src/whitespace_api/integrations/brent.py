"""Brent crude price (USD a barrel), the fuel signal for freight estimates.

From FRED (St. Louis Fed), series DCOILBRENTEU: free, no key, daily. Kept in memory for
`CACHE_HOURS`; if FRED can't be reached the last value (or a reference price) is used,
so a freight estimate never fails because of it.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, timedelta

import httpx

log = logging.getLogger(__name__)

URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
SERIES = "DCOILBRENTEU"
TIMEOUT = httpx.Timeout(10.0, connect=5.0)
CACHE_HOURS = 12
REFERENCE_USD = 80.0  # what the freight rates are calibrated at
# FRED stalls requests from bare tool user agents; a generic browser-style one is served.
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; whitespace/1.0)"}


@dataclass(frozen=True)
class Brent:
    usd: float
    as_of: date | None  # None when the reference price is used
    source: str


_cache: tuple[float, Brent] | None = None


def parse(csv: str) -> Brent | None:
    """The latest priced day. FRED marks holidays with "." (no value)."""
    for line in reversed(csv.strip().splitlines()[1:]):
        day, _, value = line.partition(",")
        try:
            return Brent(usd=float(value), as_of=date.fromisoformat(day), source="FRED")
        except ValueError:
            continue
    return None


async def latest(client: httpx.AsyncClient, *, today: date | None = None) -> Brent:
    global _cache
    now = time.monotonic()
    if _cache is not None and now - _cache[0] < CACHE_HOURS * 3600:
        return _cache[1]
    start = (today or date.today()) - timedelta(days=30)
    try:
        response = await client.get(
            URL, params={"id": SERIES, "cosd": start.isoformat()}, headers=HEADERS, timeout=TIMEOUT
        )
        response.raise_for_status()
        found = parse(response.text)
    except httpx.HTTPError as exc:
        log.warning("Brent price unavailable: %s", type(exc).__name__)
        found = None
    if found is None:
        # Keep a stale value rather than the reference; retry in an hour.
        fallback = _cache[1] if _cache else Brent(REFERENCE_USD, None, "reference")
        _cache = (now - (CACHE_HOURS - 1) * 3600, fallback)
        return fallback
    _cache = (now, found)
    return found


def reset_cache() -> None:
    """For tests."""
    global _cache
    _cache = None
