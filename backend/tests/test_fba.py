"""Amazon FBA: the fee model (pure), the unit economics, and the endpoints."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.seed import TOWELS
from tests.test_freight import FUEL, route
from tests.test_landed_cost import Source, markets, source, us_schedule  # noqa: F401  (fixtures)
from whitespace_api.schemas.fba import FbaInput
from whitespace_api.services import fba, fba_fees, freight
from whitespace_api.services.fba_fees import Parcel

# ---------- Amazon fees ----------


def test_small_standard_is_charged_on_unit_weight() -> None:
    flat = Parcel(10, 8, 0.5, 6 / 16)  # 6 oz, thin
    assert fba_fees.size_tier(flat) == "small_standard"
    fee = fba_fees.fulfilment(flat, 19.99)
    assert (fee.fee, fee.surcharge, fee.total) == (3.45, 0.12, 3.57)
    assert fba_fees.fulfilment(flat, 9.99).fee == 2.56  # low-price FBA band
    assert fba_fees.fulfilment(flat, 50.01).fee == 3.71


def test_large_standard_uses_dimensional_weight_and_steps_above_three_pounds() -> None:
    towel = Parcel(14, 10, 4, 1.6)  # 560 in³ / 139 = 4.03 lb > 1.6 lb
    fee = fba_fees.fulfilment(towel, 29.99)
    assert fee.tier == "large_standard" and fee.shipping_weight_lb == pytest.approx(4.029, 1e-3)
    assert fee.fee == pytest.approx(6.97 + 5 * 0.08)  # 1.03 lb over 3 lb: five 4-oz steps
    light = Parcel(12, 9, 2, 0.9)  # 216/139 = 1.55 lb -> the 1.5-1.75 lb band
    assert fba_fees.fulfilment(light, 20).fee == 5.57
    # Dimensional weight treats thin sides as 2 in
    assert Parcel(17, 13, 1, 0.5).dim_weight_lb == pytest.approx(17 * 13 * 2 / 139)


def test_bulky_items_are_refused_with_a_reason() -> None:
    with pytest.raises(fba_fees.NotSupportedError, match="bulky"):
        fba_fees.fulfilment(Parcel(30, 20, 10, 12), 80)


@pytest.mark.parametrize(
    ("category", "price", "fee"),
    [
        ("home_kitchen", 29.99, 4.50),
        ("home_kitchen", 1.50, 0.30),  # the minimum
        ("beauty_health", 9.99, 0.80),  # 8% at $10 or less, on the whole price
        ("beauty_health", 12.00, 1.80),
        ("clothing", 14.99, 0.75),
        ("clothing", 25.00, 4.25),
        ("electronics_accessories", 150.00, 19.00),  # 15% of 100 + 8% of 50
        ("furniture", 300.00, 40.00),  # 15% of 200 + 10% of 100
        ("jewelry", 300.00, 52.50),  # 20% of 250 + 5% of 50
        ("grocery", 2.00, 0.16),  # no minimum
    ],
)
def test_referral_fees(category: str, price: float, fee: float) -> None:
    assert fba_fees.referral(category, price) == fee


def test_storage_scales_with_volume_and_time() -> None:
    box = Parcel(12, 12, 12, 2)  # one cubic foot
    assert fba_fees.storage_per_unit(box, 1) == round(fba_fees.STORAGE_AVG, 2)
    assert fba_fees.storage_per_unit(box, 3) == round(fba_fees.STORAGE_AVG * 3, 2)


# ---------- unit economics (pure parts) ----------


@pytest.mark.parametrize(
    ("value", "fees"),
    [
        (2_000, round(2.77 + 2_000 * 0.00125, 2)),  # informal entry: flat MPF
        (5_000, round(34.58 + 5_000 * 0.00125, 2)),  # formal: the MPF minimum
        (50_000, round(50_000 * 0.003464 + 50_000 * 0.00125, 2)),
        (500_000, round(670.86 + 500_000 * 0.00125, 2)),  # the MPF maximum
    ],
)
def test_us_import_fees(value: float, fees: float) -> None:
    assert fba.import_fees(value) == fees


def test_small_orders_compare_sharing_with_a_full_box() -> None:
    assert fba._containers_for(5, "auto") == ("lcl", "20ft")
    assert fba._containers_for(20, "auto") == ("20ft", "40ft")
    assert fba._containers_for(200, "auto") == ("40ft",)
    assert fba._containers_for(5, "20ft") == ("20ft",)


BODY: dict[str, Any] = {
    "hs6": TOWELS, "origin": "PAK", "unit_cost_usd": 4.2, "price_usd": 29.99,
    "category": "home_kitchen", "length_in": 14, "width_in": 10, "height_in": 4,
    "weight_lb": 1.6, "units": 500, "monthly_sales": 150,
}  # fmt: skip


def test_break_even_is_the_first_price_that_covers_costs() -> None:
    data = FbaInput(**BODY)
    parcel = Parcel(14, 10, 4, 1.6)
    price = fba.break_even(data, parcel, landed=7.7, storage=0.6)
    assert price is not None
    assert fba._profit(data, parcel, price, 7.7, 0.6) >= 0
    assert fba._profit(data, parcel, price - 0.02, 7.7, 0.6) < 0


# ---------- the endpoints ----------


@pytest.fixture
async def us_route(
    db_sessionmaker: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fixed(http: object, **_: object) -> Any:
        return FUEL

    monkeypatch.setattr(freight.brent_feed, "latest", fixed)
    async with db_sessionmaker() as db:
        db.add(route(dest="USA", sea_nm=11_600.0, dest_port="New York", dest_port_code="USNYC"))
        await db.commit()


async def test_estimate_adds_up(
    user: AsyncClient,
    markets: None,  # noqa: F811
    source: Source,  # noqa: F811
    us_route: None,
) -> None:
    out = await user.post("/api/v1/fba/estimate", json=BODY)
    assert out.status_code == 200, out.text
    body = out.json()
    assert body["duty"]["rate_pct"] == pytest.approx(19.1)  # 9.1% + 10% (fixed schedule)
    assert body["size"]["tier"] == "large_standard"
    assert body["shipment"]["container"] in {"lcl", "20ft"}
    assert body["shipment"]["route"] == "Karachi → New York"
    costs = {c["key"]: c["usd"]["typical"] for c in body["costs"]}
    assert costs["duty"] == pytest.approx(round(4.2 * 0.191, 2))
    assert costs["referral"] == 4.50 and costs["fulfilment"] == pytest.approx(7.63)
    assert "prep" not in costs  # zero lines are left out
    total = sum(costs.values())
    assert body["total_cost_unit"]["typical"] == pytest.approx(total, abs=0.02)
    assert body["profit_unit"]["typical"] == pytest.approx(29.99 - total, abs=0.02)
    low, typical, high = (body["profit_unit"][k] for k in ("low", "typical", "high"))
    assert low <= typical <= high
    assert body["margin"]["typical"] == pytest.approx(typical / 29.99, abs=1e-3)
    assert body["break_even_price"] < 29.99 and body["payback_months"] > 0
    cash = body["first_order_cash"]["typical"]
    assert cash > 500 * 4.2 + body["shipment"]["freight_usd"]["typical"]
    assert body["verdict"]["tone"] in {"positive", "neutral"}


async def test_own_freight_quote_replaces_the_estimate(
    user: AsyncClient,
    markets: None,  # noqa: F811
    source: Source,  # noqa: F811
) -> None:
    out = await user.post("/api/v1/fba/estimate", json=BODY | {"freight_per_unit_usd": 1.0})
    assert out.status_code == 200, out.text
    body = out.json()
    assert body["shipment"]["container"] is None and body["shipment"]["route"] is None
    assert body["shipment"]["freight_usd"]["typical"] == 500.0


async def test_errors_are_explained(
    user: AsyncClient,
    markets: None,  # noqa: F811
    source: Source,  # noqa: F811
    us_route: None,
) -> None:
    bulky = await user.post("/api/v1/fba/estimate", json=BODY | {"length_in": 40})
    assert bulky.status_code == 422 and "bulky" in bulky.json()["detail"]
    no_route = await user.post("/api/v1/fba/estimate", json=BODY | {"origin": "TUR"})
    assert no_route.status_code == 404 and "route" in no_route.json()["detail"]
    too_big = await user.post("/api/v1/fba/estimate", json=BODY | {"shipping": "20ft",
                                                                    "units": 20_000})  # fmt: skip
    assert too_big.status_code == 422 and "doesn't fit" in too_big.json()["detail"]
    invalid = await user.post("/api/v1/fba/estimate", json=BODY | {"price_usd": 0})
    assert invalid.status_code == 422


async def test_public_calculator_needs_no_sign_in(
    client: AsyncClient,
    markets: None,  # noqa: F811
    source: Source,  # noqa: F811
    us_route: None,
) -> None:
    assert (await client.post("/api/v1/fba/estimate", json=BODY)).status_code == 401
    out = await client.post("/api/v1/public/fba/estimate", json=BODY)
    assert out.status_code == 200, out.text
    options = (await client.get("/api/v1/public/fba/options")).json()
    assert {"key": "home_kitchen", "label": "Home & Kitchen"} in options["categories"]
    assert options["fees_as_of"] == fba_fees.FEES_AS_OF


async def test_options_list_the_countries_we_can_ship_from(
    client: AsyncClient,
    markets: None,  # noqa: F811
    us_route: None,
) -> None:
    options = (await client.get("/api/v1/public/fba/options")).json()
    assert {"code": "PAK", "name": "Pakistan"} in options["origins"]
    found = await client.get("/api/v1/public/products/search?q=towels")
    assert found.status_code == 200 and found.json()[0]["hs6"] == TOWELS
