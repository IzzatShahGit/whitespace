"""Freight estimates: one container (or a share of one), from the exporter's port to the buyer.

A transparent model, not a quote. Every figure is a low / typical / high range:

  sea freight     base + rate per nautical mile, per 40ft, scaled by fuel (Brent)
  port & papers   origin terminal handling, customs export filing, bill of lading
  insurance       0.3% of 110% of the goods + freight value (the usual cover)
  road legs       to/from the gateway port, for landlocked countries
  arrival         destination terminal handling and delivery order

A shared container (LCL, "less than container load") is priced per cubic metre (or per
tonne, whichever is more), with the higher per-m³ rates and fixed paperwork that forwarders
charge for consolidating small shipments.

Base rates are set from public container indices and should be reviewed monthly
(`RATES_AS_OF`). The route comes from the pipeline's `ref_sea_route` table; the load
per container from a typical density for the product's HS chapter (the user can override).
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.integrations import brent as brent_feed
from whitespace_api.models.trade import MarketSupplier, SeaRoute
from whitespace_api.repositories import trade as trade_repo
from whitespace_api.schemas.freight import (
    ContainerKind,
    CostLine,
    CostRange,
    FreightEstimate,
    FreightRoute,
    FuelPrice,
    LaneInfo,
)
from whitespace_api.schemas.trade import CountryOut
from whitespace_api.services import lanes

# ---- rates (USD; review monthly against public indices such as Drewry WCI / FBX) ----
RATES_AS_OF = "2026-11"
FEU_BASE = 450.0  # fixed part of a 40ft sea rate
FEU_PER_NM = 0.24  # per nautical mile
BUNKER_SHARE = 0.30  # share of the sea rate that moves with fuel
SPREAD = (0.70, 1.50)  # low / high vs typical: spot rates swing and skew upward
ROAD_PER_KM_FEU = 1.8  # trucking a 40ft box
NM_TO_KM = 1.852


@dataclass(frozen=True)
class Box:
    label: str
    sea_factor: float  # vs a 40ft rate
    fee_factor: float  # port fees vs a 40ft
    usable_m3: float  # what fits after packing gaps
    max_kg: float  # practical payload


BOXES: dict[ContainerKind, Box] = {
    "20ft": Box("20ft container", 0.60, 0.70, 28.0, 21_000),
    "40ft": Box("40ft container", 1.00, 1.00, 58.0, 26_000),
    "40hc": Box("40ft high-cube", 1.05, 1.00, 66.0, 26_000),
}
FEU_USABLE_M3 = BOXES["40ft"].usable_m3
ORIGIN_FEES_FEU = 350.0  # terminal handling, export customs, documents
ARRIVAL_FEES_FEU = 500.0  # destination terminal handling, delivery order
INSURANCE_RATE = 0.003
INSURED_SHARE = 1.10

# Shared container (LCL), per "W/M": a cubic metre or a tonne, whichever is more; min 1.
LCL_SEA_PREMIUM = 1.5  # per m³, vs a full 40ft's rate per usable m³
LCL_ORIGIN_FIXED, LCL_ORIGIN_PER_WM = 75.0, 25.0  # papers; warehouse receiving
LCL_ARRIVAL_FIXED, LCL_ARRIVAL_PER_WM = 150.0, 45.0  # delivery order; unpacking, handling
LCL_ROAD_SHARE = 1.5  # part-loads cost more per m³ than a full truck
LCL_DEFAULT_M3 = 5.0  # a typical small first order
LCL_EXTRA_DAYS = (4, 8)  # waiting for the box to fill, unpacking at arrival

# Typical packed density (kg per m3) by HS chapter range: decides how many kg fit.
DENSITY: list[tuple[range, int, str]] = [
    (range(1, 6), 450, "meat, fish and dairy"),
    (range(6, 15), 400, "plants, fruit, vegetables and grains"),
    (range(15, 25), 650, "food and drink"),
    (range(25, 28), 1200, "minerals and fuels"),
    (range(28, 39), 650, "chemicals"),
    (range(39, 41), 400, "plastics and rubber"),
    (range(41, 44), 150, "leather goods"),
    (range(44, 47), 350, "wood"),
    (range(47, 50), 500, "paper"),
    (range(50, 56), 400, "fibres, yarn and fabric"),  # pressed bales and rolls
    (range(56, 64), 160, "textiles and clothing"),
    (range(64, 68), 130, "footwear and headwear"),
    (range(68, 72), 900, "stone, ceramics and glass"),
    (range(72, 84), 1100, "metals"),
    (range(84, 86), 250, "machines and electronics"),
    (range(86, 90), 150, "vehicles"),
    (range(90, 93), 200, "instruments"),
    (range(93, 98), 120, "furniture, toys and other goods"),
]
DEFAULT_DENSITY = (300, "general goods")


class NoRouteError(Exception):
    """No sea route between these countries. The message is safe to show."""


def density(hs6: str) -> tuple[int, str]:
    chapter = int(hs6[:2])
    return next(((d, k) for r, d, k in DENSITY if chapter in r), DEFAULT_DENSITY)


def typical_load(hs6: str, box: Box | None) -> tuple[float, str]:
    """Kg in a typical full box, or in a typical small shared shipment (`box` None)."""
    kg_m3, kind = density(hs6)
    if box is None:
        kg = kg_m3 * LCL_DEFAULT_M3
        return round(kg, -1), f"A typical small order of {kind} (about {LCL_DEFAULT_M3:g} m³)"
    kg = min(box.max_kg, kg_m3 * box.usable_m3)
    limit = "weight limit" if kg == box.max_kg else f"about {kg_m3} kg per m³"
    return round(kg, -1), f"A typical load for {kind} ({limit})"


def spread(typical: float, low: float = SPREAD[0], high: float = SPREAD[1]) -> CostRange:
    return CostRange(
        low=round(typical * low, 2), typical=round(typical, 2), high=round(typical * high, 2)
    )


def add(*ranges: CostRange) -> CostRange:
    return CostRange(
        low=round(sum(r.low for r in ranges), 2),
        typical=round(sum(r.typical for r in ranges), 2),
        high=round(sum(r.high for r in ranges), 2),
    )


def per_kg(r: CostRange, kg: float) -> CostRange:
    return CostRange(
        low=round(r.low / kg, 4), typical=round(r.typical / kg, 4), high=round(r.high / kg, 4)
    )


def fuel_factor(brent_usd: float) -> float:
    return round(1 - BUNKER_SHARE + BUNKER_SHARE * brent_usd / brent_feed.REFERENCE_USD, 3)


def transit_days(sea_nm: float, inland_km: int) -> tuple[int, int]:
    """Sailing at 12-16 knots plus port time (and transhipment on the slow end)."""
    road = inland_km / 500
    if sea_nm == 0:
        return max(1, round(road)), max(2, round(road * 1.6 + 1))
    low = sea_nm / (16 * 24) + 3 + road
    high = sea_nm / (12 * 24) + 9 + road * 1.6
    return round(low), round(high)


def build(
    *,
    origin: CountryOut,
    dest: CountryOut,
    route: SeaRoute,
    reverse: bool,
    hs6: str,
    container: ContainerKind,
    kg: float | None,
    value_usd_kg: float | None,
    value_basis: str | None,
    fuel: brent_feed.Brent,
    volume_m3: float | None = None,
) -> FreightEstimate:
    """The estimate itself. Pure: no database or network.

    `volume_m3`: the load's measured volume; without it, volume follows from the
    product's typical packed density."""
    shared = container == "lcl"
    box = None if shared else BOXES[container]
    if kg is None:
        kg, kg_basis = typical_load(hs6, box)
    else:
        kg_basis = "Your figure"
    volume = volume_m3 or kg / density(hs6)[0]
    if box is None:
        wm = max(1.0, volume, kg / 1000)  # what a shared box is charged on
        sea_mult = LCL_SEA_PREMIUM * wm / FEU_USABLE_M3
        road_mult = min(1.0, LCL_ROAD_SHARE * wm / FEU_USABLE_M3)
        origin_fees = LCL_ORIGIN_FIXED + LCL_ORIGIN_PER_WM * wm
        arrival_fees = LCL_ARRIVAL_FIXED + LCL_ARRIVAL_PER_WM * wm
    else:
        sea_mult, road_mult = box.sea_factor, box.fee_factor
        origin_fees = ORIGIN_FEES_FEU * box.fee_factor
        arrival_fees = ARRIVAL_FEES_FEU * box.fee_factor
    origin_port, dest_port = route.origin_port, route.dest_port
    origin_km, dest_km = route.origin_inland_km, route.dest_inland_km
    if reverse:
        origin_port, dest_port = dest_port, origin_port
        origin_km, dest_km = dest_km, origin_km

    factor = fuel_factor(fuel.usd)
    direction = lanes.lane(origin.code, dest.code)
    lines: list[CostLine] = []
    if origin_km:
        lines.append(
            CostLine(
                key="origin_road",
                label=f"Road/rail to {origin_port} (~{origin_km:,} km)",
                stage="to_port",
                usd=spread(origin_km * ROAD_PER_KM_FEU * road_mult, 0.75, 1.4),
            )
        )
    lines.append(
        CostLine(
            key="origin_fees",
            label=(
                "Warehouse, customs and papers at origin"
                if shared
                else "Port handling, customs and papers at origin"
            ),
            stage="to_port",
            usd=spread(origin_fees, 0.75, 1.4),
        )
    )
    if route.sea_nm > 0:
        sea = (FEU_BASE + FEU_PER_NM * route.sea_nm) * factor * direction.factor * sea_mult
        lines.append(
            CostLine(
                key="sea",
                label=f"Sea freight {origin_port} → {dest_port} (incl. fuel"
                + (", return-direction rate)" if direction.direction == "backhaul" else ")"),
                stage="to_port",
                usd=spread(sea),
            )
        )
    freight_so_far = add(*(line.usd for line in lines))
    if value_usd_kg:
        goods = value_usd_kg * kg
        lines.append(
            CostLine(
                key="insurance",
                label="Cargo insurance (0.3% of 110% of value)",
                stage="to_port",
                usd=CostRange(
                    low=round((goods + freight_so_far.low) * INSURED_SHARE * INSURANCE_RATE, 2),
                    typical=round(
                        (goods + freight_so_far.typical) * INSURED_SHARE * INSURANCE_RATE, 2
                    ),
                    high=round((goods + freight_so_far.high) * INSURED_SHARE * INSURANCE_RATE, 2),
                ),
            )
        )
    lines.append(
        CostLine(
            key="arrival_fees",
            label=(
                f"Unpacking, handling and release at {dest_port}"
                if shared
                else f"Port handling and release at {dest_port}"
            ),
            stage="after_arrival",
            usd=spread(arrival_fees, 0.75, 1.5),
        )
    )
    if dest_km:
        lines.append(
            CostLine(
                key="dest_road",
                label=f"Road/rail from {dest_port} (~{dest_km:,} km)",
                stage="after_arrival",
                usd=spread(dest_km * ROAD_PER_KM_FEU * road_mult, 0.75, 1.4),
            )
        )

    to_port = add(*(line.usd for line in lines if line.stage == "to_port"))
    after = add(*(line.usd for line in lines if line.stage == "after_arrival"))
    total = add(to_port, after)
    days_low, days_high = transit_days(route.sea_nm, origin_km + dest_km)
    if shared:
        days_low, days_high = days_low + LCL_EXTRA_DAYS[0], days_high + LCL_EXTRA_DAYS[1]

    notes = [
        "An estimate from distance, fuel and typical port fees, not a quote: ask two or "
        "three freight forwarders before you price a deal.",
    ]
    if direction.direction == "backhaul" and route.sea_nm > 0:
        notes.append(
            f"Ships from {direction.origin_region} to {direction.dest_region} often sail "
            "part-empty, so rates this way are lower: sea freight is priced at "
            f"{direction.factor:.0%} of the busy direction."
        )
    if shared:
        twenty = BOXES["20ft"]
        if volume > twenty.usable_m3 or kg > twenty.max_kg:
            notes.append(
                f"About {volume:.0f} m³ is more than a 20ft container holds: at this size a "
                "full container is usually cheaper than sharing."
            )
        else:
            full = build(
                origin=origin, dest=dest, route=route, reverse=reverse, hs6=hs6,
                container="20ft", kg=kg, value_usd_kg=value_usd_kg,
                value_basis=value_basis, fuel=fuel, volume_m3=volume_m3,
            ).total.typical  # fmt: skip
            notes.append(
                f"About {volume:.1f} m³ shares a container with other shippers. A whole 20ft "
                f"would cost about ${full:,.0f} all-in"
                + (", less than sharing: book a full one." if full <= total.typical else ".")
            )
    if fuel.source != "FRED":
        notes.append("Live fuel prices were unavailable, so a reference oil price was used.")
    if not value_usd_kg:
        notes.append("Insurance isn't included: enter your price to add it.")
    if route.sea_nm == 0:
        notes.append("Both countries use the same port, so only the road/rail legs count.")
    elif route.sea_nm < 800:
        notes.append("Neighbouring countries often ship by road or rail, which can be cheaper.")
    if origin_km or dest_km:
        notes.append("Road distances to gateway ports are approximate.")
    notes.append("Duties, import VAT and the buyer's local delivery are not included here.")

    return FreightEstimate(
        origin=origin,
        dest=dest,
        route=FreightRoute(
            origin_port=origin_port,
            dest_port=dest_port,
            sea_nm=round(route.sea_nm),
            sea_km=round(route.sea_nm * NM_TO_KM),
            origin_inland_km=origin_km,
            dest_inland_km=dest_km,
            days_low=days_low,
            days_high=days_high,
        ),
        container=container,
        kg_per_container=kg,
        volume_m3=round(volume, 1),
        kg_basis=kg_basis,
        value_usd_kg=value_usd_kg,
        value_basis=value_basis,
        fuel=FuelPrice(
            brent_usd=round(fuel.usd, 2), as_of=fuel.as_of, source=fuel.source, factor=factor
        ),
        lines=lines,
        to_port=to_port,
        after_arrival=after,
        total=total,
        to_port_usd_kg=per_kg(to_port, kg),
        total_usd_kg=per_kg(total, kg),
        lane=LaneInfo(direction=direction.direction, factor=direction.factor),
        rates_as_of=RATES_AS_OF,
        notes=notes,
    )


async def _route(db: AsyncSession, origin: str, dest: str) -> tuple[SeaRoute, bool] | None:
    """The stored route and whether it's stored the other way round."""
    found = await db.get(SeaRoute, (origin, dest))
    if found is not None:
        return found, False
    back = await db.get(SeaRoute, (dest, origin))
    return (back, True) if back is not None else None


async def origins_to(db: AsyncSession, dest: str) -> list[CountryOut]:
    """Countries we can price shipping from to `dest` (routes are stored one way)."""
    rows = await db.execute(
        select(SeaRoute.origin, SeaRoute.dest).where(
            (SeaRoute.dest == dest) | (SeaRoute.origin == dest)
        )
    )
    codes = {o if d == dest else d for o, d in rows.all()} - {dest}
    names = await trade_repo.countries_by_code(db, list(codes))
    return sorted(
        (CountryOut(code=c, name=names[c].name) for c in codes if c in names),
        key=lambda c: c.name,
    )


async def _value(
    db: AsyncSession, *, origin: str, dest: str, hs6: str
) -> tuple[float | None, str | None]:
    """What the destination pays the origin per kg (customs data), else its average."""
    row = await db.scalar(
        select(MarketSupplier.unit_price_usd_kg).where(
            MarketSupplier.market == dest,
            MarketSupplier.hs6 == hs6,
            MarketSupplier.supplier == origin,
        )
    )
    if row:
        return float(row), "What this market pays this supplier (customs data)"
    found = await trade_repo.get_opportunity(db, exporter=origin, hs6=hs6, market=dest)
    price = found.MarketOpportunity.market_unit_price_usd_kg if found else None
    if price:
        return float(price), "This market's average import price (customs data)"
    return None, None


async def _inputs(
    db: AsyncSession, http: httpx.AsyncClient, *, origin: str, dest: str, hs6: str
) -> tuple[CountryOut, CountryOut, SeaRoute, bool, brent_feed.Brent]:
    """Everything `build` needs from the database and the fuel feed, fetched once."""
    countries = await trade_repo.countries_by_code(db, [origin, dest])
    if origin not in countries or dest not in countries:
        raise NoRouteError("Unknown country")
    if await trade_repo.get_product(db, hs6) is None:
        raise NoRouteError(f"Unknown product {hs6}")
    found = await _route(db, origin, dest)
    if found is None:
        raise NoRouteError(
            f"We don't have a shipping route between {countries[origin].name} and "
            f"{countries[dest].name} yet."
        )
    route, reverse = found
    return (
        CountryOut(code=origin, name=countries[origin].name),
        CountryOut(code=dest, name=countries[dest].name),
        route,
        reverse,
        await brent_feed.latest(http),
    )


async def estimate(
    db: AsyncSession,
    http: httpx.AsyncClient,
    *,
    origin: str,
    dest: str,
    hs6: str,
    container: ContainerKind = "40ft",
    kg: float | None = None,
    value_usd_kg: float | None = None,
) -> FreightEstimate:
    source, target, route, reverse, fuel = await _inputs(
        db, http, origin=origin, dest=dest, hs6=hs6
    )
    basis = "Your price" if value_usd_kg else None
    if not value_usd_kg:
        value_usd_kg, basis = await _value(db, origin=origin, dest=dest, hs6=hs6)
    return build(
        origin=source, dest=target, route=route, reverse=reverse, hs6=hs6,
        container=container, kg=kg, value_usd_kg=value_usd_kg, value_basis=basis, fuel=fuel,
    )  # fmt: skip


async def options(
    db: AsyncSession,
    http: httpx.AsyncClient,
    *,
    origin: str,
    dest: str,
    hs6: str,
    kg: float,
    volume_m3: float,
    value_usd_kg: float,
    containers: tuple[ContainerKind, ...],
) -> dict[ContainerKind, FreightEstimate]:
    """One shipment priced several ways (e.g. shared vs a full 20ft), one lookup."""
    source, target, route, reverse, fuel = await _inputs(
        db, http, origin=origin, dest=dest, hs6=hs6
    )
    return {
        kind: build(
            origin=source,
            dest=target,
            route=route,
            reverse=reverse,
            hs6=hs6,
            container=kind,
            kg=kg,
            value_usd_kg=value_usd_kg,
            value_basis="Your price",
            fuel=fuel,
            volume_m3=volume_m3,
        )
        for kind in containers
    }
