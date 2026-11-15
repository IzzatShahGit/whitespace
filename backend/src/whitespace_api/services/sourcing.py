"""Buying: which countries to source a product from, explained with measured facts.

Every tag, signal and pick is computed from customs data (world exports, growth, price
per kg as value/weight, markets served). Thresholds are named here so they can be tuned.
"""

from __future__ import annotations

from statistics import median
from typing import Any

from sqlalchemy import Row
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.models.trade import SupplierLandscape
from whitespace_api.repositories import trade as repo
from whitespace_api.schemas.sourcing import (
    CurrentSupplier,
    SourceProductMatch,
    SourceSignal,
    SourcingPage,
    SourcingPick,
    SupplierOption,
)
from whitespace_api.schemas.trade import CountryOut
from whitespace_api.services import trade as trade_service
from whitespace_api.services.explain import percent

GROWTH_YEARS = 3
# Price vs the median of the listed suppliers
CHEAP = -0.10
PRICEY = 0.10
# Export growth per year
GROWING = 0.05
SHRINKING = -0.05
# Reliability: how many markets buy at least $100k a year from the supplier
WIDELY_TRUSTED = 50
ESTABLISHED = 15
# Picks ignore tiny suppliers whose prices and growth are noisy
PICK_MIN_MARKETS = 10
PICK_MIN_SHARE = 0.01


class SourcingNotFoundError(Exception):
    """The buyer or product isn't in the data. Safe to show."""


def kg(price: float) -> str:
    return f"${price:.2f}/kg"


def _signals(row: Any, median_price: float | None) -> list[SourceSignal]:
    out: list[SourceSignal] = []
    price = row.unit_price_usd_kg
    if price is not None and median_price:
        diff = price / median_price - 1
        if diff <= CHEAP:
            out.append(
                SourceSignal(tone="positive", text=f"{percent(-diff)} below the median price")
            )
        elif diff >= PRICEY:
            out.append(SourceSignal(tone="neutral", text=f"{percent(diff)} above the median price"))
        else:
            out.append(SourceSignal(tone="neutral", text="Close to the median price"))
    growth = row.exports_growth_3y
    if growth is not None:
        if growth >= GROWING:
            out.append(SourceSignal(tone="positive", text=f"Exports grew {percent(growth)} a year"))
        elif growth <= SHRINKING:
            out.append(
                SourceSignal(tone="negative", text=f"Exports fell {percent(-growth)} a year")
            )
        else:
            out.append(SourceSignal(tone="neutral", text="Exports steady"))
    served = row.markets_served
    tone = "positive" if served >= WIDELY_TRUSTED else "neutral"
    out.append(SourceSignal(tone=tone, text=f"Sells to {served} markets"))
    return out


def _option(
    row: Row[SupplierLandscape, str], median_price: float | None, yours: dict[str, float]
) -> SupplierOption:
    s = row.SupplierLandscape
    return SupplierOption(
        country=CountryOut(code=s.supplier, name=row.supplier_name),
        rank=s.rank,
        exports_usd=s.exports_usd,
        world_share=s.world_share,
        exports_growth_3y=s.exports_growth_3y,
        markets_served=s.markets_served,
        unit_price_usd_kg=s.unit_price_usd_kg,
        supplies_you_share=yours.get(s.supplier),
        tags=[],
        signals=_signals(s, median_price),
    )


def _picks(
    options: list[SupplierOption],
    median_price: float | None,
    current: list[CurrentSupplier],
    buyer: CountryOut,
    start_year: int,
) -> list[SourcingPick]:
    picks: list[SourcingPick] = []
    solid = [o for o in options if o.markets_served >= PICK_MIN_MARKETS]

    priced = [o for o in solid if o.unit_price_usd_kg is not None]
    if priced and median_price:
        best = min(priced, key=lambda o: o.unit_price_usd_kg or 0)
        price = best.unit_price_usd_kg or 0
        below = max(0.0, 1 - price / median_price)
        best.tags.append("Lowest price")
        picks.append(
            SourcingPick(
                kind="best_value",
                title="Best value",
                country=best.country,
                reason=(
                    f"{best.country.name} sells at {kg(price)}, {percent(below)} below the "
                    f"median of {kg(median_price)}, to {best.markets_served} markets."
                ),
            )
        )

    if options:
        top = max(options, key=lambda o: o.markets_served)
        top.tags.append("Most established")
        picks.append(
            SourcingPick(
                kind="most_established",
                title="Most established",
                country=top.country,
                reason=(
                    f"{top.country.name} supplies {top.markets_served} markets and "
                    f"{percent(top.world_share)} of world exports."
                ),
            )
        )

    rising = [
        o
        for o in solid
        if o.world_share >= PICK_MIN_SHARE and (o.exports_growth_3y or 0) >= GROWING
    ]
    if rising:
        fast = max(rising, key=lambda o: o.exports_growth_3y or 0)
        fast.tags.append("Fastest growing")
        picks.append(
            SourcingPick(
                kind="rising",
                title="Rising supplier",
                country=fast.country,
                reason=(
                    f"{fast.country.name}'s exports grew {percent(fast.exports_growth_3y or 0)} "
                    f"a year since {start_year}."
                ),
            )
        )

    if current:
        lead = current[0]
        at_price = f" at {kg(lead.unit_price_usd_kg)}" if lead.unit_price_usd_kg else ""
        picks.append(
            SourcingPick(
                kind="current",
                title="Supplies you today",
                country=lead.country,
                reason=(
                    f"{lead.country.name} supplies {percent(lead.share)} of "
                    f"{buyer.name}'s imports{at_price}."
                ),
            )
        )
    return picks


async def sourcing(db: AsyncSession, *, buyer: str, hs6: str) -> SourcingPage:
    buyer_row = await repo.get_country(db, buyer)
    if buyer_row is None:
        raise SourcingNotFoundError(f"Unknown country {buyer}")
    try:
        product = await trade_service.get_product(db, hs6)
    except trade_service.NotFoundError as exc:
        raise SourcingNotFoundError(str(exc)) from exc
    rows = [r for r in await repo.landscape(db, hs6) if r.SupplierLandscape.supplier != buyer]
    if not rows:
        raise SourcingNotFoundError("No supplier data for this product yet")

    buyer_out = CountryOut(code=buyer_row.code, name=buyer_row.name)
    current = [
        CurrentSupplier(
            country=CountryOut(code=r.MarketSupplier.supplier, name=r.supplier_name),
            share=r.MarketSupplier.share_end,
            unit_price_usd_kg=r.MarketSupplier.unit_price_usd_kg,
        )
        for r in await repo.market_suppliers(db, market=buyer, hs6=hs6)
    ]
    prices = [p for r in rows if (p := r.SupplierLandscape.unit_price_usd_kg) is not None]
    median_price = median(prices) if prices else None
    yours = {c.country.code: c.share for c in current}
    options = [_option(r, median_price, yours) for r in rows]
    for option in options:
        if option.supplies_you_share:
            option.tags.append("Supplies you today")

    data_year = await repo.latest_data_year(db) or 0
    return SourcingPage(
        buyer=buyer_out,
        product=product,
        data_year=data_year,
        median_price_usd_kg=median_price,
        picks=_picks(options, median_price, current, buyer_out, data_year - GROWTH_YEARS),
        suppliers=options,
        current_suppliers=current,
    )


async def search_products(db: AsyncSession, *, q: str, limit: int) -> list[SourceProductMatch]:
    """Products to buy: everyday names first, then word matches (buy mode)."""
    matches = await trade_service.search_products_by_mode(db, q=q, limit=limit, exporter=None)
    return [
        SourceProductMatch(hs6=m.hs6, description=m.description, suppliers=m.markets)
        for m in matches
    ]
