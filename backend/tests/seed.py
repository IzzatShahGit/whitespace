"""A small trade dataset for API tests: Pakistan, three products, a few markets."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from whitespace_api.models import Country, MarketOpportunity, MarketSupplier, Product

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
                ),
                MarketSupplier(
                    market="DEU",
                    hs6=TOWELS,
                    supplier="PAK",
                    value_usd=4e6,
                    share_start=0.2,
                    share_end=0.2,
                ),
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
