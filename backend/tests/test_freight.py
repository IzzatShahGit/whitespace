"""Freight estimates: the cost model, the fuel feed, and the endpoint."""

from __future__ import annotations

from datetime import date

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.seed import TOWELS
from whitespace_api.integrations import brent
from whitespace_api.models.trade import SeaRoute
from whitespace_api.schemas.trade import CountryOut
from whitespace_api.services import freight, lanes

PAK = CountryOut(code="PAK", name="Pakistan")
DEU = CountryOut(code="DEU", name="Germany")
FUEL = brent.Brent(usd=80.0, as_of=date(2026, 11, 11), source="FRED")


def route(**extra: object) -> SeaRoute:
    fields: dict[str, object] = {
        "origin": "PAK", "dest": "DEU", "sea_nm": 6400.0,
        "origin_port": "Karachi", "origin_port_code": "PKKHI",
        "dest_port": "Bremerhaven", "dest_port_code": "DEBRV",
        "origin_inland_km": 0, "dest_inland_km": 0,
    } | extra  # fmt: skip
    return SeaRoute(**fields)


def build(**extra: object) -> freight.FreightEstimate:
    args: dict[str, object] = {
        "origin": PAK, "dest": DEU, "route": route(), "reverse": False, "hs6": TOWELS,
        "container": "40ft", "kg": None, "value_usd_kg": 5.0, "value_basis": "Your price",
        "fuel": FUEL,
    } | extra  # fmt: skip
    return freight.build(**args)  # type: ignore[arg-type]


def test_sea_rate_scales_with_distance_and_fuel() -> None:
    e = build()
    sea = next(line for line in e.lines if line.key == "sea")
    assert sea.usd.typical == pytest.approx(450 + 0.24 * 6400)  # at the reference fuel price
    assert sea.usd.low < sea.usd.typical < sea.usd.high
    dearer = build(fuel=brent.Brent(usd=120.0, as_of=None, source="FRED"))
    assert next(x for x in dearer.lines if x.key == "sea").usd.typical == pytest.approx(
        (450 + 0.24 * 6400) * 1.15
    )  # 30% of the rate moves with fuel: +50% oil -> +15%


def test_totals_split_at_the_port_and_per_kg() -> None:
    e = build()
    assert e.kg_per_container == 9280  # textiles, 160 kg/m3 x 58 m3
    assert e.to_port.typical + e.after_arrival.typical == pytest.approx(e.total.typical)
    assert e.to_port_usd_kg.typical == pytest.approx(e.to_port.typical / 9280, abs=1e-4)
    assert {line.key for line in e.lines} == {"origin_fees", "sea", "insurance", "arrival_fees"}
    assert 18 <= e.route.days_low < e.route.days_high <= 35


def test_twenty_foot_dense_goods_hit_the_weight_limit() -> None:
    e = build(container="20ft", hs6="720810")  # steel: weight, not space, is the limit
    assert e.kg_per_container == 21_000 and "weight limit" in e.kg_basis
    own = build(kg=5000.0)
    assert own.kg_per_container == 5000 and own.kg_basis == "Your figure"


def test_shared_container_is_priced_per_cubic_metre() -> None:
    small = build(container="lcl")  # textiles: 5 m3 at 160 kg/m3
    assert small.kg_per_container == 800 and small.volume_m3 == 5.0
    sea = next(x for x in small.lines if x.key == "sea").usd.typical
    full_sea = 450 + 0.24 * 6400
    assert sea == pytest.approx(full_sea / 58 * 1.5 * 5, abs=0.01)
    assert small.total.typical < build(container="20ft").total.typical
    # ...but dearer per kg, and slower (consolidation)
    assert small.total_usd_kg.typical > build(container="20ft").total_usd_kg.typical
    assert small.route.days_low > build().route.days_low
    assert any("shares a container" in n for n in small.notes)


def test_big_shared_shipments_suggest_a_full_box() -> None:
    near_full = build(container="lcl", kg=4000.0)  # 25 m3: sharing costs more than a 20ft
    assert any("less than sharing" in n for n in near_full.notes)
    too_big = build(container="lcl", kg=6000.0)  # 37.5 m3: more than a 20ft holds
    assert any("more than a 20ft" in n for n in too_big.notes)
    heavy = build(container="lcl", hs6="720810", kg=3000.0)  # steel: charged per tonne
    sea = next(x for x in heavy.lines if x.key == "sea").usd.typical
    assert sea == pytest.approx((450 + 0.24 * 6400) / 58 * 1.5 * 3, abs=0.01)


def test_backhaul_lanes_are_cheaper() -> None:
    there = build()  # Pakistan -> Germany: with the flow
    back = build(origin=DEU, dest=PAK, reverse=True)  # against it
    assert there.lane.direction == "headhaul" and back.lane.direction == "backhaul"
    sea = {e.lane.direction: next(x for x in e.lines if x.key == "sea") for e in (there, back)}
    assert sea["backhaul"].usd.typical == pytest.approx(sea["headhaul"].usd.typical * 0.8)
    assert any("part-empty" in n for n in back.notes)
    assert lanes.lane("USA", "CHN").factor == 0.4  # floor
    assert lanes.lane("DEU", "FRA").direction == "balanced"


def test_reverse_route_and_landlocked_road_leg() -> None:
    e = build(route=route(dest_inland_km=900), reverse=True, value_usd_kg=None)
    assert e.route.origin_port == "Bremerhaven" and e.route.dest_port == "Karachi"
    assert e.route.origin_inland_km == 900 and e.route.dest_inland_km == 0
    assert any(line.key == "origin_road" for line in e.lines)
    assert all(line.key != "insurance" for line in e.lines)
    assert any("Insurance isn't included" in n for n in e.notes)


async def test_brent_feed_parses_and_falls_back() -> None:
    brent.reset_cache()
    csv = "observation_date,DCOILBRENTEU\n2026-11-10,90.16\n2026-11-11,92.14\n2026-11-12,.\n"
    transport = httpx.MockTransport(lambda r: httpx.Response(200, text=csv))
    async with httpx.AsyncClient(transport=transport) as http:
        got = await brent.latest(http)
    assert got.usd == 92.14 and got.as_of == date(2026, 11, 11)

    brent.reset_cache()
    down = httpx.MockTransport(lambda r: httpx.Response(503))
    async with httpx.AsyncClient(transport=down) as http:
        got = await brent.latest(http)
    assert got.source == "reference" and got.usd == brent.REFERENCE_USD
    brent.reset_cache()


@pytest.fixture
async def stored_route(
    db_sessionmaker: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fixed(http: object, **_: object) -> brent.Brent:
        return FUEL

    monkeypatch.setattr(freight.brent_feed, "latest", fixed)
    async with db_sessionmaker() as db:
        db.add(route())
        await db.commit()


async def test_endpoint_both_directions(user: AsyncClient, stored_route: None) -> None:
    out = await user.get(f"/api/v1/freight?origin=PAK&dest=DEU&hs6={TOWELS}")
    assert out.status_code == 200
    body = out.json()
    assert body["route"]["origin_port"] == "Karachi" and body["container"] == "40ft"
    assert body["value_basis"] is None  # the seed has no price for this pair: no insurance
    priced = await user.get(f"/api/v1/freight?origin=PAK&dest=DEU&hs6={TOWELS}&value_usd_kg=5")
    assert priced.json()["value_basis"] == "Your price"
    assert any(line["key"] == "insurance" for line in priced.json()["lines"])

    back = await user.get(f"/api/v1/freight?origin=DEU&dest=PAK&hs6={TOWELS}&container=20ft")
    assert back.status_code == 200 and back.json()["route"]["origin_port"] == "Bremerhaven"


async def test_endpoint_errors(user: AsyncClient, stored_route: None) -> None:
    missing = await user.get(f"/api/v1/freight?origin=THA&dest=USA&hs6={TOWELS}")
    assert missing.status_code == 404 and "route" in missing.json()["detail"]
    bad = await user.get(f"/api/v1/freight?origin=PAK&dest=DEU&hs6={TOWELS}&container=10ft")
    assert bad.status_code == 422


async def test_requires_sign_in(client: AsyncClient) -> None:
    assert (
        await client.get(f"/api/v1/freight?origin=PAK&dest=DEU&hs6={TOWELS}")
    ).status_code == 401
