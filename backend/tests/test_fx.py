"""Exchange rates: one cached call to the free service, every currency in one payload."""

from __future__ import annotations

from collections.abc import Callable, Iterator

import httpx
import pytest
from httpx import AsyncClient

from whitespace_api.core.http import http_client
from whitespace_api.integrations import fx
from whitespace_api.main import app

RATES = {"result": "success", "time_last_update_utc": "Mon, 16 Nov 2026 00:02:31 +0000"}
UseService = Callable[[Callable[[httpx.Request], httpx.Response]], list[str]]


@pytest.fixture
def rates_service() -> Iterator[UseService]:
    """Point the API's outbound client at a fake rates service; start with an empty cache."""
    fx._cache = None

    def use(handler: Callable[[httpx.Request], httpx.Response]) -> list[str]:
        calls: list[str] = []

        def record(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return handler(request)

        fake = httpx.AsyncClient(transport=httpx.MockTransport(record))
        app.dependency_overrides[http_client] = lambda: fake
        return calls

    yield use
    fx._cache = None


async def test_requires_sign_in(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/fx")).status_code == 401


async def test_all_rates_in_one_cached_payload(
    user: AsyncClient, rates_service: UseService
) -> None:
    calls = rates_service(
        lambda r: httpx.Response(
            200, json={**RATES, "rates": {"USD": 1, "PKR": 280.5, "EUR": 0.86}}
        )
    )
    response = await user.get("/api/v1/fx")
    assert response.status_code == 200
    assert response.headers["cache-control"].startswith("private")
    assert response.json() == {
        "base": "USD",
        "rates": {"USD": 1, "PKR": 280.5, "EUR": 0.86},
        "updated": RATES["time_last_update_utc"],
        "source": "ExchangeRate-API",
    }
    await user.get("/api/v1/fx")
    assert len(calls) == 1  # the second request was served from the cache


async def test_service_down_and_nothing_cached(
    user: AsyncClient, rates_service: UseService
) -> None:
    rates_service(lambda r: httpx.Response(503))
    assert (await user.get("/api/v1/fx")).status_code == 503


async def test_service_error_payload_is_not_cached(
    user: AsyncClient, rates_service: UseService
) -> None:
    rates_service(lambda r: httpx.Response(200, json={"result": "error"}))
    assert (await user.get("/api/v1/fx")).status_code == 503
    assert fx._cache is None


async def test_stale_rates_beat_no_rates() -> None:
    good = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={**RATES, "rates": {"PKR": 280.0}})
        )
    )
    down = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    fx._cache = None
    try:
        first = await fx.rates(good, now=0)
        later = await fx.rates(down, now=fx.CACHE_SECONDS + 1)  # expired, refresh fails
        assert later is first and later.per_usd["PKR"] == 280.0
    finally:
        fx._cache = None
