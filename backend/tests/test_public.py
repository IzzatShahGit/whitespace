"""The signed-out preview on the landing page: works without sign-in, limited, validated."""

from __future__ import annotations

from httpx import AsyncClient

from tests.seed import TOWELS
from whitespace_api.api.v1.routes import public
from whitespace_api.core.ratelimit import RateLimiter


async def test_preview_without_signing_in(client: AsyncClient, seeded: None) -> None:
    response = await client.get("/api/v1/public/preview", params={"exporter": "PAK", "q": "towels"})
    assert response.status_code == 200
    assert response.headers["cache-control"].startswith("public")
    body = response.json()
    assert body["product"]["hs6"] == TOWELS and body["product"]["name"] == "towels"
    assert [m["market"]["code"] for m in body["markets"]] == ["THA", "DEU", "USA"]
    assert body["total"] == 3 and body["data_year"] == 2024


async def test_preview_validation(client: AsyncClient, seeded: None) -> None:
    get = client.get
    assert (await get("/api/v1/public/preview?exporter=PAK&q=x")).status_code == 422
    assert (await get("/api/v1/public/preview?exporter=pak&q=towels")).status_code == 422
    assert (await get("/api/v1/public/preview?exporter=FRA&q=towels")).status_code == 404
    assert (await get("/api/v1/public/preview?exporter=PAK&q=xqzvbk")).status_code == 404


async def test_preview_is_rate_limited(client: AsyncClient, seeded: None, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(public, "_preview_limit", RateLimiter(per_minute=2))
    url = "/api/v1/public/preview?exporter=PAK&q=towels"
    codes = [(await client.get(url)).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    other = await client.get(url, headers={"x-forwarded-for": "203.0.113.9"})
    assert other.status_code == 200  # limits are per caller


def test_limiter_window_and_memory_bound() -> None:
    limiter = RateLimiter(per_minute=1, max_keys=2)
    assert limiter.allow("a", now=0) and not limiter.allow("a", now=30)
    assert limiter.allow("a", now=61)  # the window slid
    limiter.allow("b", now=61)
    limiter.allow("c", now=61)
    assert len(limiter._hits) == 2  # oldest key evicted
