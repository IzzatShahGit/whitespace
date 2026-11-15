"""Market search API against a small seeded dataset in the test database."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.seed import BED_LINEN, THREAD, TOWELS


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/countries/exporters",
        "/api/v1/products/search?exporter=PAK&q=towels",
        f"/api/v1/markets?exporter=PAK&hs6={TOWELS}",
        f"/api/v1/markets/DEU?exporter=PAK&hs6={TOWELS}",
    ],
)
async def test_requires_sign_in(client: AsyncClient, seeded: None, path: str) -> None:
    assert (await client.get(path)).status_code == 401


async def test_exporters(user: AsyncClient) -> None:
    response = await user.get("/api/v1/countries/exporters")
    assert response.json() == [
        {"code": "BGD", "name": "Bangladesh"},
        {"code": "PAK", "name": "Pakistan"},
    ]


@pytest.mark.parametrize(
    "q,first",
    [
        ("cotton bed sheets", BED_LINEN),
        ("bedsheets", BED_LINEN),  # only the everyday-name dictionary knows this word
        ("towels", TOWELS),
        ("6302", BED_LINEN),
        ("towell", TOWELS),
    ],
)
async def test_product_search(user: AsyncClient, q: str, first: str) -> None:
    response = await user.get("/api/v1/products/search", params={"exporter": "PAK", "q": q})
    assert response.status_code == 200
    results = response.json()
    assert results and results[0]["hs6"] == first


async def test_misleading_typos_return_nothing(user: AsyncClient) -> None:
    results = (await user.get("/api/v1/products/search?exporter=PAK&q=xqzvbk")).json()
    assert results == []


async def test_search_hides_products_without_markets(user: AsyncClient) -> None:
    # Sewing thread matches "cotton" but Pakistan has no ranked markets for it here.
    results = (await user.get("/api/v1/products/search?exporter=PAK&q=cotton")).json()
    assert THREAD not in [r["hs6"] for r in results]


async def test_search_validation_and_unknown_exporter(user: AsyncClient) -> None:
    assert (await user.get("/api/v1/products/search?exporter=PAK&q=t")).status_code == 422
    assert (await user.get("/api/v1/products/search?exporter=pak&q=towels")).status_code == 422
    missing = await user.get("/api/v1/products/search?exporter=FRA&q=towels")
    assert missing.status_code == 404


async def test_ranked_markets(user: AsyncClient) -> None:
    response = await user.get("/api/v1/markets", params={"exporter": "PAK", "hs6": TOWELS})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, max-age=300"
    page = response.json()
    assert page["total"] == 3
    assert page["data"] == {"start_year": 2021, "end_year": 2024, "version": "BACI-HS17-V202601"}
    assert [i["market"]["name"] for i in page["items"]] == ["Thailand", "Germany", "United States"]
    assert [i["label"] for i in page["items"]] == ["Strong", "Good", "Watch"]
    assert page["items"][0]["reasons"] == [
        "Imports grew 19% a year from 2021 to 2024",
        "China's share fell 9 points since 2021",
        "Pakistan holds under 1% of this market: room to grow",
    ]
    assert page["items"][2]["top_rival"] is None


async def test_pagination(user: AsyncClient) -> None:
    second = (await user.get(f"/api/v1/markets?exporter=PAK&hs6={TOWELS}&limit=1&offset=1")).json()
    assert [i["market"]["code"] for i in second["items"]] == ["DEU"]
    assert second["total"] == 3
    past_end = (await user.get(f"/api/v1/markets?exporter=PAK&hs6={TOWELS}&offset=50")).json()
    assert past_end["items"] == [] and past_end["total"] == 3


async def test_product_with_no_markets(user: AsyncClient) -> None:
    page = (await user.get(f"/api/v1/markets?exporter=PAK&hs6={THREAD}")).json()
    assert page["total"] == 0 and page["items"] == [] and page["data"] is None


async def test_markets_errors(user: AsyncClient) -> None:
    assert (await user.get("/api/v1/markets?exporter=PAK&hs6=999999")).status_code == 404
    assert (await user.get("/api/v1/markets?exporter=PAK&hs6=63026")).status_code == 422
    assert (await user.get(f"/api/v1/markets?exporter=FRA&hs6={TOWELS}")).status_code == 404


async def test_market_detail(user: AsyncClient) -> None:
    response = await user.get(f"/api/v1/markets/DEU?exporter=PAK&hs6={TOWELS}")
    assert response.status_code == 200
    detail = response.json()
    assert detail["market"]["rank"] == 2
    assert detail["market"]["reasons"][2] == "Pakistan already holds 24% of this market"
    assert [s["country"]["name"] for s in detail["suppliers"]] == ["China", "Pakistan"]
    assert detail["suppliers"][0]["share_start"] == 0.8


async def test_market_detail_not_ranked(user: AsyncClient) -> None:
    response = await user.get(f"/api/v1/markets/CHN?exporter=PAK&hs6={TOWELS}")
    assert response.status_code == 404
