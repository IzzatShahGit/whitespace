"""Import duties and landed cost for a product in a market: you against your rivals.

Rule one: no invented numbers. Every rate comes from a source with its year
(WITS-TRAINS everywhere; the UK Trade Tariff for the UK). A preference counts only when
the data records it for the country itself, or for a group the country is confirmed to
be in (`whitespace_shared.tariff_schemes`). Otherwise the standard (MFN) rate is shown,
labelled "a trade preference may apply": precision over coverage.

Landed cost = FOB price + freight and insurance + duty. Most markets charge duty on the
CIF value (goods plus freight and insurance); those in `FOB_VALUATION` on the FOB value.
Prices are customs value / weight (FOB), the same basis as a seller's cost.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.core.config import Settings
from whitespace_api.integrations import tariffs
from whitespace_api.integrations.monthly_trade import EU_MEMBERS
from whitespace_api.repositories import tariffs as repo
from whitespace_api.repositories import trade as trade_repo
from whitespace_api.schemas.landed_cost import (
    DutyComparison,
    DutyRate,
    LandedCost,
    LandedLine,
    RivalDuty,
    StandardRate,
)
from whitespace_api.schemas.trade import CountryOut, ProductOut
from whitespace_api.services import pricing
from whitespace_api.services import trade as trade_service
from whitespace_api.services.explain import EN_DASH
from whitespace_api.services.sourcing import kg
from whitespace_shared.tariff_schemes import schemes_for

log = logging.getLogger(__name__)

TOP_RIVALS = 5
SOURCE_NAMES = {"wits": "WITS-TRAINS (World Bank, UNCTAD)", "uk": "UK Trade Tariff"}
# Customs value is FOB (no international freight or insurance) in these markets.
FOB_VALUATION = frozenset({"USA", "CAN", "AUS", "NZL"})
MAY_APPLY = "Standard rate; a trade preference may apply."
EU_INTERNAL = "EU single market"
NOT_INCLUDED = "Not included: anti-dumping and other trade-defence duties, VAT and excise."
US_EXTRA = (
    "US rates are the general or trade-agreement rate: additional US tariffs by country "
    "(HTS chapter 99) may apply on top and are not included. See https://hts.usitc.gov/"
)
NO_FREIGHT = "Excludes freight: add your shipping and insurance cost per kg."


class NotCoveredError(Exception):
    """No duty data for this market and product. The message is safe to show."""


class UnavailableError(Exception):
    """The source can't be reached and nothing is cached. The message is safe to show."""


@dataclass(frozen=True)
class Freight:
    """Freight and insurance to the market: a share of the FOB value, or USD per kg."""

    pct: float | None = None
    usd_kg: float | None = None

    @property
    def given(self) -> bool:
        return self.pct is not None or self.usd_kg is not None

    def per_kg(self, fob: float) -> float:
        return fob * self.pct / 100 if self.pct is not None else self.usd_kg or 0.0


@dataclass(frozen=True)
class _Tariffs:
    """A cached payload, read: every partner's rows, and the MFN row everyone falls back to."""

    source: str
    url: str
    rows: list[tariffs.TariffRow]
    mfn: tariffs.TariffRow


# ---------- wording ----------
def _number(value: float) -> str:
    return f"{value:.1f}".removesuffix(".0")


def rate_text(value: float) -> str:
    """12.0 -> "12%", 9.6 -> "9.6%"."""
    return f"{_number(value)}%"


def basis(duty: DutyRate) -> str:
    """How a rate applies, e.g. "EU GSP+, 2017" or "standard rate, 2023"."""
    label = duty.scheme or ("preferential rate" if duty.kind == "preference" else "standard rate")
    return f"{label}, {duty.year}"


def _summary(
    exporter: CountryOut,
    market: CountryOut,
    product: ProductOut,
    yours: DutyRate,
    rival: RivalDuty | None,
) -> str:
    charges = (
        f"{market.name} charges {exporter.name} {rate_text(yours.rate_pct)} on {product.name} "
        f"({basis(yours)})"
    )
    if rival is None:
        return f"{charges}."
    both = f"{charges} and {rival.country.name} {rate_text(rival.rate_pct)} ({basis(rival)})"
    gap = rival.advantage_pts
    if gap > 0:
        return f"{both}: a {_number(gap)}-point duty advantage for {exporter.name}."
    if gap < 0:
        return f"{both}: {exporter.name} pays {_number(-gap)} points more."
    return f"{both}: no duty advantage either way."


def _note(row: tariffs.TariffRow, data: _Tariffs) -> str | None:
    parts = [MAY_APPLY] if row["kind"] == "MFN" and data.source == "wits" else []
    if row["year"] < data.mfn["year"]:
        parts.append(f"Last recorded in {row['year']}; it may have changed since.")
    if row["min_rate"] != row["max_rate"]:
        lines = row["lines"] - row["na_lines"]
        low, high = _number(row["min_rate"]), _number(row["max_rate"])
        parts.append(f"Average of {lines} tariff lines ({low}{EN_DASH}{high}%).")
    if row["na_lines"]:
        parts.append(
            f"{row['na_lines']} of {row['lines']} tariff lines charge per unit: not included."
        )
    return " ".join(parts) or None


# ---------- duties ----------
def _priced(row: tariffs.TariffRow) -> bool:
    return row["lines"] > row["na_lines"]  # at least one line with a percentage duty


def _read(payload: dict[str, Any]) -> _Tariffs | None:
    rows: list[tariffs.TariffRow] = payload["rows"]
    mfn = next((r for r in rows if r["kind"] == "MFN" and _priced(r)), None)
    if mfn is None:
        return None
    return _Tariffs(source=payload["source"], url=payload["url"], rows=rows, mfn=mfn)


def duty_for(country: CountryOut, data: _Tariffs, *, market: str, reporter: str) -> DutyRate:
    """The rate `country` pays: its own or a confirmed group's preference, if lower than
    the MFN rate; otherwise the MFN rate, labelled. Pure."""
    source = SOURCE_NAMES[data.source]
    if market in EU_MEMBERS and country.code in EU_MEMBERS:
        return DutyRate(
            country=country, rate_pct=0.0, kind="preference", scheme=EU_INTERNAL,
            year=data.mfn["year"], source="EU customs union",
            note="No customs duties between EU members.",
        )  # fmt: skip
    groups = {s.group: s.name for s in schemes_for(reporter, country.code)}
    offers = [
        r
        for r in data.rows
        if r["kind"] == "PREF"
        and _priced(r)
        and (r["partner"] == country.code or r["partner"] in groups)
    ]
    best = min(offers, key=lambda r: (r["rate"], -r["year"]), default=None)
    if best is not None and best["rate"] < data.mfn["rate"]:
        return DutyRate(
            country=country, rate_pct=best["rate"], kind="preference",
            scheme=groups.get(best["partner"]) or best["scheme"], year=best["year"],
            source=source, note=_note(best, data),
        )  # fmt: skip
    return DutyRate(
        country=country, rate_pct=data.mfn["rate"], kind="standard", scheme=None,
        year=data.mfn["year"], source=source, note=_note(data.mfn, data),
    )  # fmt: skip


async def _load(
    db: AsyncSession, http: httpx.AsyncClient, *, reporter: str, hs6: str, settings: Settings
) -> tuple[dict[str, Any], datetime, bool]:
    """The cached payload, refreshed when old; the old copy if the source is down."""
    cached = await repo.get_cached(db, reporter, hs6)
    fresh_after = datetime.now(UTC) - timedelta(days=settings.tariff_cache_days)
    if cached is not None and cached.fetched_at >= fresh_after:
        return cached.payload, cached.fetched_at, False
    try:
        fetched = await tariffs.fetch(http, reporter, hs6)
    except tariffs.SourceError as exc:
        log.warning("Tariff refresh failed for %s/%s: %s", reporter, hs6, exc)
        if cached is None:
            raise UnavailableError("The tariff data source isn't responding") from exc
        return cached.payload, cached.fetched_at, True  # an older rate, labelled stale
    row = await repo.save_cached(
        db, reporter=reporter, hs6=hs6, source=fetched["source"], payload=dict(fetched)
    )
    return row.payload, row.fetched_at, False


async def _compare(
    db: AsyncSession,
    http: httpx.AsyncClient,
    *,
    exporter: str,
    market: str,
    hs6: str,
    settings: Settings,
) -> tuple[DutyComparison, dict[str, float]]:
    """The duty comparison, and each rival's average price per kg into the market."""
    you = await trade_service.get_exporter(db, exporter)
    product = await trade_service.get_product(db, hs6)
    country = await trade_repo.get_country(db, market)
    if country is None:
        raise trade_service.NotFoundError(f"Unknown country {market}")
    place = CountryOut(code=country.code, name=country.name)
    reporter = tariffs.reporter_for(market)
    if market == exporter or reporter is None:
        raise NotCoveredError(f"No import duty data for {place.name}")
    payload, fetched_at, stale = await _load(
        db, http, reporter=reporter, hs6=hs6, settings=settings
    )
    data = _read(payload)
    if data is None:
        raise NotCoveredError(
            f"No percentage import duty is recorded for this product in {place.name}"
        )

    yours = duty_for(you, data, market=market, reporter=reporter)
    suppliers = [
        s
        for s in await trade_repo.market_suppliers(db, market=market, hs6=hs6)
        if s.MarketSupplier.supplier != exporter
    ][:TOP_RIVALS]
    rivals: list[RivalDuty] = []
    prices: dict[str, float] = {}
    for s in suppliers:
        rival = CountryOut(code=s.MarketSupplier.supplier, name=s.supplier_name)
        duty = duty_for(rival, data, market=market, reporter=reporter)
        rivals.append(
            RivalDuty(
                **duty.model_dump(),
                share=s.MarketSupplier.share_end,
                advantage_pts=round(duty.rate_pct - yours.rate_pct, 2),
            )
        )
        if s.MarketSupplier.unit_price_usd_kg is not None:
            prices[rival.code] = s.MarketSupplier.unit_price_usd_kg
    main = rivals[0] if rivals else None
    comparison = DutyComparison(
        exporter=you,
        market=place,
        product=product,
        yours=yours,
        standard=StandardRate(
            rate_pct=data.mfn["rate"], year=data.mfn["year"], source=SOURCE_NAMES[data.source]
        ),
        rivals=rivals,
        main_rival=main.country if main else None,
        advantage_pts=main.advantage_pts if main else None,
        summary=_summary(you, place, product, yours, main),
        notes=([US_EXTRA] if market == "USA" else []) + [NOT_INCLUDED],
        source_url=data.url,
        fetched_at=fetched_at,
        stale=stale,
    )
    return comparison, prices


async def duties(
    db: AsyncSession,
    http: httpx.AsyncClient,
    *,
    exporter: str,
    market: str,
    hs6: str,
    settings: Settings,
) -> DutyComparison:
    """What `market` charges on a product from `exporter` and from its largest rivals."""
    comparison, _ = await _compare(
        db, http, exporter=exporter, market=market, hs6=hs6, settings=settings
    )
    return comparison


# ---------- landed cost ----------
def landed_line(
    country: CountryOut, fob: float, duty_pct: float, freight: Freight, *, fob_valuation: bool
) -> LandedLine:
    """Delivered cost per kg. Pure."""
    shipping = freight.per_kg(fob)
    customs_value = fob if fob_valuation else fob + shipping
    duty = customs_value * duty_pct / 100
    return LandedLine(
        country=country, fob_usd_kg=fob, freight_usd_kg=shipping, duty_pct=duty_pct,
        duty_usd_kg=duty, landed_usd_kg=fob + shipping + duty,
    )  # fmt: skip


def _landed_sentence(
    market: CountryOut, yours: LandedLine | None, rival: LandedLine | None, freight: Freight
) -> str | None:
    def one(line: LandedLine) -> str:
        duty = rate_text(line.duty_pct)
        return f"{kg(line.landed_usd_kg)} (from {kg(line.fob_usd_kg)}, {duty} duty)"

    parts = ([f"yours {one(yours)}"] if yours else []) + (
        [f"{rival.country.name}'s {one(rival)}"] if rival else []
    )
    if not parts:
        return None
    if freight.pct is not None:
        shipping = f"with {rate_text(freight.pct)} freight"
    elif freight.usd_kg is not None:
        shipping = f"with {kg(freight.usd_kg)} freight"
    else:
        shipping = "before freight"
    return f"Landed cost in {market.name}, {shipping}: {'; '.join(parts)}."


async def landed_cost(
    db: AsyncSession,
    http: httpx.AsyncClient,
    *,
    exporter: str,
    market: str,
    hs6: str,
    settings: Settings,
    cost_usd_kg: float | None = None,
    freight: Freight = Freight(),
) -> LandedCost:
    """Your delivered cost per kg against your rivals', and against what the market pays."""
    comparison, prices = await _compare(
        db, http, exporter=exporter, market=market, hs6=hs6, settings=settings
    )
    fob_valuation = market in FOB_VALUATION
    yours = (
        landed_line(
            comparison.exporter,
            cost_usd_kg,
            comparison.yours.rate_pct,
            freight,
            fob_valuation=fob_valuation,
        )
        if cost_usd_kg
        else None
    )
    rivals = [
        landed_line(
            r.country, prices[r.country.code], r.rate_pct, freight, fob_valuation=fob_valuation
        )
        for r in comparison.rivals
        if r.country.code in prices
    ]
    found = await trade_repo.get_opportunity(db, exporter=exporter, hs6=hs6, market=market)
    opportunity = found.MarketOpportunity if found else None
    market_price = opportunity.market_unit_price_usd_kg if opportunity else None
    check = (
        pricing.check_price(
            value_usd=cost_usd_kg,
            quantity_kg=1.0,
            market_price=market_price,
            market=comparison.market.name,
        )
        if cost_usd_kg
        else None
    )
    explanation = [comparison.summary]
    if sentence := _landed_sentence(
        comparison.market, yours, rivals[0] if rivals else None, freight
    ):
        explanation.append(sentence)
    if check and check.verdict:
        explanation.append(check.verdict)
    return LandedCost(
        duties=comparison,
        duty_base="FOB" if fob_valuation else "CIF",
        freight_pct=freight.pct,
        freight_usd_kg=freight.usd_kg,
        yours=yours,
        rivals=rivals,
        market_price_usd_kg=market_price,
        price_year=opportunity.data_year if opportunity else await trade_repo.latest_data_year(db),
        margin=1 - cost_usd_kg / market_price if cost_usd_kg and market_price else None,
        tone=check.tone if check else None,
        verdict=check.verdict if check else None,
        explanation=explanation,
        notes=comparison.notes + ([] if freight.given else [NO_FREIGHT]),
    )
