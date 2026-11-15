"""Browsing by niche against the seeded dataset (towels + bed linen = home textiles)."""

from __future__ import annotations

from httpx import AsyncClient

from tests.seed import BED_LINEN, TOWELS


async def test_niches_grouped_with_counts(user: AsyncClient) -> None:
    sectors = (await user.get("/api/v1/niches?exporter=PAK")).json()
    assert sectors[0]["name"] == "Textiles & apparel"
    counts = {n["slug"]: n["products"] for s in sectors for n in s["niches"]}
    assert counts["home-textiles"] == 2  # towels and bed linen are both 6302xx
    assert counts["towels"] == 1
    assert counts["socks"] == 0


async def test_niche_detail_lists_products_best_first(user: AsyncClient) -> None:
    detail = (await user.get("/api/v1/niches/home-textiles?exporter=PAK")).json()
    assert detail["name"] == "Bed, bath & kitchen linen"
    assert detail["exporter"]["code"] == "PAK"
    # Towels' best market scores 0.85, bed linen's 0.72.
    assert [p["product"]["hs6"] for p in detail["products"]] == [TOWELS, BED_LINEN]
    best = detail["products"][0]
    assert best["markets"] == 3
    assert best["best"]["market"]["name"] == "Thailand" and best["best"]["rank"] == 1


async def test_niche_errors(user: AsyncClient) -> None:
    assert (await user.get("/api/v1/niches/not-a-niche?exporter=PAK")).status_code == 404
    assert (await user.get("/api/v1/niches/socks?exporter=FRA")).status_code == 404
    assert (await user.get("/api/v1/niches/BAD_SLUG?exporter=PAK")).status_code == 422


async def test_niches_require_sign_in(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/niches?exporter=PAK")).status_code == 401
