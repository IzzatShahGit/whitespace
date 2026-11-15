"""Buying: where to source a product."""

from __future__ import annotations

import httpx
import pytest
from httpx import AsyncClient

from tests.seed import THREAD, TOWELS


async def page(user: AsyncClient, buyer: str = "DEU", hs6: str = TOWELS) -> httpx.Response:
    return await user.get("/api/v1/sourcing", params={"buyer": buyer, "hs6": hs6})


async def test_requires_sign_in(client: AsyncClient) -> None:
    assert (await page(client)).status_code == 401
    assert (await client.get("/api/v1/sourcing/products/search?q=towels")).status_code == 401


async def test_picks_explain_where_to_buy(user: AsyncClient) -> None:
    response = await page(user)
    assert response.status_code == 200
    assert response.headers["cache-control"].startswith("private")
    body = response.json()
    assert body["median_price_usd_kg"] == pytest.approx(3.25)  # CHN 4, PAK 3, BGD 3.5, THA 1
    picks = {p["kind"]: p for p in body["picks"]}
    assert picks["best_value"]["country"]["code"] == "PAK"
    assert "$3.00/kg" in picks["best_value"]["reason"]
    assert picks["most_established"]["country"]["code"] == "CHN"
    assert picks["rising"]["country"]["code"] == "BGD"  # PAK grows too, BGD faster
    assert picks["current"]["country"]["code"] == "CHN"
    assert "50% of Germany's imports at $4.20/kg" in picks["current"]["reason"]


async def test_buyer_is_never_its_own_supplier(user: AsyncClient) -> None:
    body = (await page(user)).json()
    assert [s["country"]["code"] for s in body["suppliers"]] == ["CHN", "PAK", "BGD", "THA"]


async def test_tiny_suppliers_are_listed_but_never_picked(user: AsyncClient) -> None:
    body = (await page(user)).json()
    thailand = next(s for s in body["suppliers"] if s["country"]["code"] == "THA")
    assert any("below the median price" in s["text"] for s in thailand["signals"])
    assert thailand["tags"] == []
    assert all(p["country"]["code"] != "THA" for p in body["picks"])


async def test_current_suppliers_are_marked(user: AsyncClient) -> None:
    body = (await page(user)).json()
    assert [(c["country"]["code"], c["share"]) for c in body["current_suppliers"]] == [
        ("CHN", 0.5),
        ("PAK", 0.2),
    ]
    pakistan = next(s for s in body["suppliers"] if s["country"]["code"] == "PAK")
    assert pakistan["supplies_you_share"] == 0.2
    assert set(pakistan["tags"]) == {"Lowest price", "Supplies you today"}


async def test_no_current_suppliers_means_no_current_pick(user: AsyncClient) -> None:
    body = (await page(user, buyer="USA")).json()
    assert body["current_suppliers"] == []
    assert "current" not in {p["kind"] for p in body["picks"]}
    assert len(body["suppliers"]) == 5  # Germany is a supplier for everyone else


async def test_unknown_inputs(user: AsyncClient) -> None:
    assert (await page(user, buyer="XXX")).status_code == 404
    assert (await page(user, hs6=THREAD)).status_code == 404  # product without supplier data
    assert (await page(user, hs6="999999")).status_code == 404
    assert (await page(user, hs6="12")).status_code == 422
    assert (await page(user, buyer="deu")).status_code == 422


async def test_buy_search_lists_only_products_with_suppliers(user: AsyncClient) -> None:
    results = (await user.get("/api/v1/sourcing/products/search?q=cotton")).json()
    assert [(r["hs6"], r["suppliers"]) for r in results] == [(TOWELS, 5)]
