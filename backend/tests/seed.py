"""A small trade dataset for API tests: Pakistan, three products, a few markets.

Towels also have a world supplier landscape (for buying): Thailand is the cheapest but
tiny, so it must never be picked; Germany buys from China and Pakistan today.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from whitespace_api.models import (
    Country,
    MarketOpportunity,
    MarketSupplier,
    Product,
    SupplierLandscape,
)

TOWELS, BED_LINEN, THREAD = "630260", "630231", "520411"


def opportunity(
    market: str, hs6: str, rank: int, score: float, **extra: object
) -> MarketOpportunity:
    values: dict[str, object] = {
        "exporter": "PAK",
        "market": market,
        "hs6": hs6,
        "data_year": 2024,
        "market_imports_usd": 164e6,
        "import_growth_3y": 0.19,
        "top_rival": "CHN",
        "top_rival_share_change": -0.09,
        "exporter_share": 0.002,
        "exporter_rca": 116.0,
        "score": score,
        "rank": rank,
        "data_version": "BACI-HS17-V202601",
    }
    values.update(extra)
    return MarketOpportunity(**values)


def source(
    supplier: str, rank: int, share: float, growth: float, served: int, price: float
) -> SupplierLandscape:
    return SupplierLandscape(
        hs6=TOWELS,
        supplier=supplier,
        rank=rank,
        exports_usd=share * 12e9,
        exports_growth_3y=growth,
        world_share=share,
        markets_served=served,
        unit_price_usd_kg=price,
    )


@pytest.fixture
async def seeded(db_sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    async with db_sessionmaker() as s:
        s.add_all(
            [
                Country(code=c, name=n)
                for c, n in [
                    ("PAK", "Pakistan"),
                    ("BGD", "Bangladesh"),
                    ("CHN", "China"),
                    ("DEU", "Germany"),
                    ("THA", "Thailand"),
                    ("USA", "United States"),
                ]
            ]
            + [
                Product(
                    hs6=TOWELS,
                    description=(
                        "Kitchen and toilet linen: of terry towelling or similar terry fabrics, "
                        "of cotton"
                    ),
                    hs_revision="HS17",
                ),
                Product(
                    hs6=BED_LINEN,
                    description="Bed linen: of cotton (not printed, knitted or crocheted)",
                    hs_revision="HS17",
                ),
                Product(
                    hs6=THREAD,
                    description="Cotton: sewing thread, containing 85% or more by weight of cotton",
                    hs_revision="HS17",
                ),
                opportunity("THA", TOWELS, 1, 0.85),
                opportunity("DEU", TOWELS, 2, 0.60, exporter_share=0.235),
                opportunity("USA", TOWELS, 3, 0.40, top_rival=None, top_rival_share_change=None),
                opportunity("USA", BED_LINEN, 1, 0.72),
                opportunity("THA", TOWELS, 1, 0.70, exporter="BGD"),
                MarketSupplier(
                    market="DEU",
                    hs6=TOWELS,
                    supplier="CHN",
                    value_usd=10e6,
                    share_start=0.8,
                    share_end=0.5,
                    unit_price_usd_kg=4.2,
                ),
                MarketSupplier(
                    market="DEU",
                    hs6=TOWELS,
                    supplier="PAK",
                    value_usd=4e6,
                    share_start=0.2,
                    share_end=0.2,
                ),
                source("CHN", 1, 0.40, 0.02, 150, 4.0),
                source("PAK", 2, 0.12, 0.06, 120, 3.0),
                source("BGD", 3, 0.03, 0.15, 40, 3.5),
                source("DEU", 4, 0.02, -0.08, 90, 9.0),
                source("THA", 5, 0.0005, 0.50, 5, 1.0),
            ]
        )
        await s.commit()


@pytest.fixture
async def user(client: AsyncClient, seeded: None) -> AsyncIterator[AsyncClient]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "ahmed@example.com", "full_name": "Ahmed", "password": "towels-2026!"},
    )
    assert response.status_code == 201
    yield client
