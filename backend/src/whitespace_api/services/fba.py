"""Is a product worth importing and selling on Amazon US with FBA? Unit economics.

One product, bought from one country, sold on Amazon US. Per unit sold:

    landed   = supplier price + freight + duty (US extras included) + import fees + prep
    amazon   = referral fee + fulfilment fee (with fuel surcharge) + storage
    selling  = advertising + returns
    profit   = price - landed - amazon - selling

Freight comes from our estimator (sea route, fuel, port fees) priced on the order's real
volume, as a low / typical / high range; everything else is a single figure. Only the
inputs the seller sets are assumptions (ads, returns, US shipment fees, monthly sales),
and the page shows them as such. Nothing is stored: the result is computed per request.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.core.config import Settings
from whitespace_api.schemas.fba import (
    AmazonSize,
    FbaCost,
    FbaEstimate,
    FbaInput,
    FbaShipment,
    FbaVerdict,
)
from whitespace_api.schemas.freight import ContainerKind, CostRange, FreightEstimate
from whitespace_api.services import fba_fees, freight, landed_cost
from whitespace_api.services import trade as trade_service
from whitespace_api.services.fba_fees import Parcel

MARKET = "USA"
M3_PER_FT3 = 0.0283168
KG_PER_LB = 0.453592
CARTON_VOLUME = 1.10  # master cartons and gaps around the units
CARTON_WEIGHT = 1.05
# US import fees (CBP, from 1 October 2026). Formal entry above $2,500.
MPF_RATE, MPF_MIN, MPF_MAX = 0.003464, 34.58, 670.86
MPF_INFORMAL, INFORMAL_LIMIT = 2.77, 2_500.0
HMF_RATE = 0.00125  # harbour maintenance, sea shipments
LCL_MAX_M3 = 15.0  # above this a full container is usually cheaper than sharing
# Rule of thumb many sellers use for net margin after every cost.
STRONG_MARGIN, WORKABLE_MARGIN = 0.25, 0.15

SIZE_LABELS = {"small_standard": "Small standard", "large_standard": "Large standard"}


@dataclass(frozen=True)
class _Freight:
    total: CostRange  # whole shipment
    container: ContainerKind | None
    containers: int
    label: str
    estimate: FreightEstimate | None


def _r(value: float) -> CostRange:
    return CostRange(low=value, typical=value, high=value)


def _scale(r: CostRange, factor: float, digits: int = 2) -> CostRange:
    return CostRange(
        low=round(r.low * factor, digits),
        typical=round(r.typical * factor, digits),
        high=round(r.high * factor, digits),
    )


def _sum(*ranges: CostRange) -> CostRange:
    return CostRange(
        low=round(sum(r.low for r in ranges), 2),
        typical=round(sum(r.typical for r in ranges), 2),
        high=round(sum(r.high for r in ranges), 2),
    )


def import_fees(value_usd: float) -> float:
    """CBP's merchandise processing fee plus the harbour maintenance fee, one sea entry."""
    if value_usd <= INFORMAL_LIMIT:
        mpf = MPF_INFORMAL
    else:
        mpf = min(MPF_MAX, max(MPF_MIN, value_usd * MPF_RATE))
    return round(mpf + value_usd * HMF_RATE, 2)


def _containers_for(volume: float, choice: str) -> tuple[ContainerKind, ...]:
    if choice != "auto":
        return (choice,)  # type: ignore[return-value]
    if volume <= LCL_MAX_M3:
        return ("lcl", "20ft")
    if volume <= freight.BOXES["20ft"].usable_m3:
        return ("20ft", "40ft")
    return ("40ft",)


async def _freight(
    db: AsyncSession, http: httpx.AsyncClient, data: FbaInput, *, kg: float, volume: float
) -> _Freight:
    if data.freight_per_unit_usd is not None:
        return _Freight(_r(round(data.freight_per_unit_usd * data.units, 2)), None, 1,
                        "Your forwarder's quote", None)  # fmt: skip
    kinds = _containers_for(volume, data.shipping)
    boxes = 1
    if kinds == ("40ft",):  # very large orders: several full 40ft boxes
        boxes = max(1, math.ceil(volume / freight.BOXES["40ft"].usable_m3))
    elif kinds[0] in freight.BOXES:
        box = freight.BOXES[kinds[0]]
        if volume > box.usable_m3 * 1.0001 or kg > box.max_kg:
            raise fba_fees.NotSupportedError(
                f"About {volume:.0f} m³ doesn't fit in one {box.label}: choose Automatic."
            )
    found = await freight.options(
        db, http, origin=data.origin, dest=MARKET, hs6=data.hs6, kg=kg / boxes,
        volume_m3=volume / boxes, value_usd_kg=data.unit_cost_usd * data.units / kg,
        containers=kinds,
    )  # fmt: skip
    kind, best = min(found.items(), key=lambda item: item[1].total.typical)
    label = "Shared container (LCL)" if kind == "lcl" else freight.BOXES[kind].label
    if boxes > 1:
        label = f"{boxes} x {label}"
    return _Freight(_scale(best.total, boxes), kind, boxes, label, best)


def _profit(data: FbaInput, parcel: Parcel, price: float, landed: float, storage: float) -> float:
    """Typical profit per unit at `price`, for the break-even search."""
    amazon = fba_fees.referral(data.category, price) + fba_fees.fulfilment(parcel, price).total
    selling = price * data.ad_pct / 100 + landed * data.return_pct / 100
    return price - landed - amazon - storage - selling


def break_even(data: FbaInput, parcel: Parcel, landed: float, storage: float) -> float | None:
    """The lowest price (to the cent) that covers every cost, or None above $10,000."""
    low, high = 0.01, 10_000.0
    if _profit(data, parcel, high, landed, storage) < 0:
        return None
    for _ in range(40):  # fee bands make it stepwise, so bisect rather than solve
        mid = (low + high) / 2
        if _profit(data, parcel, mid, landed, storage) >= 0:
            high = mid
        else:
            low = mid
    return round(math.ceil(high * 100) / 100, 2)


def _verdict(data: FbaInput, margin: CostRange, roi: CostRange, cover: float) -> FbaVerdict:
    m = margin.typical
    if m < 0:
        tone, headline = "negative", "Loses money at this price"
    elif m < WORKABLE_MARGIN:
        tone, headline = "negative", "Margin too thin to absorb surprises"
    elif m < STRONG_MARGIN:
        tone, headline = "neutral", "Workable, if your costs hold"
    else:
        tone, headline = "positive", "Healthy margin"
    reasons = [
        f"{m:.0%} net margin and {roi.typical:.0%} return on landed cost, typical freight "
        f"(from {margin.low:.0%} to {margin.high:.0%})."
    ]
    if margin.low < 0 <= m:
        reasons.append("If freight comes in at the high end, this loses money.")
    if data.price_usd < 10:
        reasons.append("Under $10 leaves little room: ads and returns eat most of it.")
    if cover > fba_fees.AGED_AFTER_MONTHS:
        reasons.append(
            f"{cover:.0f} months of stock: units older than 6 months pay Amazon's "
            "aged-inventory surcharge. Order less, or ship in two lots."
        )
    return FbaVerdict(tone=tone, headline=headline, reasons=reasons)


async def estimate(
    db: AsyncSession, http: httpx.AsyncClient, data: FbaInput, *, settings: Settings
) -> FbaEstimate:
    parcel = Parcel(data.length_in, data.width_in, data.height_in, data.weight_lb)
    fulfil = fba_fees.fulfilment(parcel, data.price_usd)  # refuses bulky items first
    product = await trade_service.get_product(db, data.hs6)
    duty = await landed_cost.import_duty(
        db, http, origin=data.origin, market=MARKET, hs6=data.hs6, settings=settings
    )
    units = data.units
    kg = round(units * data.weight_lb * KG_PER_LB * CARTON_WEIGHT, 1)
    volume = round(units * parcel.cubic_feet * M3_PER_FT3 * CARTON_VOLUME, 2)
    shipped = await _freight(db, http, data, kg=kg, volume=volume)
    goods_value = data.unit_cost_usd * units
    fees_entry = import_fees(goods_value)
    duty_unit = round(data.unit_cost_usd * duty.duty.rate_pct / 100, 2)  # US: on FOB value

    cover = units / data.monthly_sales
    storage = fba_fees.storage_per_unit(parcel, max(cover / 2, 0.5))
    referral = fba_fees.referral(data.category, data.price_usd)
    freight_unit = _scale(shipped.total, 1 / units)
    fixed_unit = (fees_entry + data.us_shipment_fees_usd) / units

    landed = _sum(
        _r(data.unit_cost_usd), freight_unit, _r(duty_unit), _r(round(fixed_unit, 2)),
        _r(data.prep_usd),
    )  # fmt: skip
    ads = round(data.price_usd * data.ad_pct / 100, 2)
    returns = _scale(landed, data.return_pct / 100)
    amazon = round(referral + fulfil.total + storage, 2)
    total = _sum(landed, _r(amazon), _r(ads), returns)
    profit = CostRange(
        low=round(data.price_usd - total.high, 2),
        typical=round(data.price_usd - total.typical, 2),
        high=round(data.price_usd - total.low, 2),
    )
    margin = _scale(profit, 1 / data.price_usd, 4)
    roi = CostRange(
        low=round(profit.low / landed.high, 4),
        typical=round(profit.typical / landed.typical, 4),
        high=round(profit.high / landed.low, 4),
    )
    monthly = CostRange(
        low=round(profit.low * data.monthly_sales - fba_fees.PROFESSIONAL_PLAN_USD, 2),
        typical=round(profit.typical * data.monthly_sales - fba_fees.PROFESSIONAL_PLAN_USD, 2),
        high=round(profit.high * data.monthly_sales - fba_fees.PROFESSIONAL_PLAN_USD, 2),
    )
    upfront = units * (data.unit_cost_usd + duty_unit + data.prep_usd) + fees_entry
    cash = _sum(
        shipped.total,
        _r(round(upfront + data.us_shipment_fees_usd + fba_fees.PROFESSIONAL_PLAN_USD, 2)),
    )
    payback = round(cash.typical / monthly.typical, 1) if monthly.typical > 0 else None

    category = fba_fees.CATEGORIES[data.category].label
    duty_note = " + ".join(
        [landed_cost.rate_text(duty.duty.base_pct)]
        + [f"{landed_cost.rate_text(a.rate_pct)} {a.name}" for a in duty.duty.additional]
    )
    costs = [
        FbaCost(key="product", label="Product (supplier price)", group="landed",
                 usd=_r(data.unit_cost_usd)),
        FbaCost(key="freight", label=f"Freight to the US ({shipped.label})", group="landed",
                 usd=freight_unit),
        FbaCost(key="duty", label=f"US import duty {landed_cost.rate_text(duty.duty.rate_pct)}",
                 group="landed", usd=_r(duty_unit), note=duty_note),
        FbaCost(key="import_fees", label="Customs fees, broker and delivery to Amazon",
                 group="landed", usd=_r(round(fixed_unit, 2)),
                 note=f"${fees_entry:,.2f} CBP fees + ${data.us_shipment_fees_usd:,.0f} "
                 "broker and delivery, shared across the order"),
        FbaCost(key="prep", label="Labels and prep", group="landed", usd=_r(data.prep_usd)),
        FbaCost(key="referral", label=f"Amazon referral fee ({category})",
                 group="amazon", usd=_r(referral)),
        FbaCost(key="fulfilment", label=f"FBA fulfilment fee ({SIZE_LABELS[fulfil.tier]})",
                 group="amazon", usd=_r(fulfil.total),
                 note=f"${fulfil.fee:.2f} + ${fulfil.surcharge:.2f} fuel surcharge"),
        FbaCost(key="storage", label="Amazon storage", group="amazon", usd=_r(storage),
                 note=f"About {cover:.1f} months of stock at the year's average rate"),
        FbaCost(key="ads", label=f"Advertising ({data.ad_pct:g}% of sales)", group="selling",
                 usd=_r(ads)),
        FbaCost(key="returns", label=f"Returns ({data.return_pct:g}% of units)",
                 group="selling", usd=returns, note="Assumes returned units can't be resold"),
    ]  # fmt: skip
    if not data.prep_usd:
        costs = [c for c in costs if c.key != "prep"]

    est = shipped.estimate
    notes = [
        "Your inputs drive this: supplier price, selling price, monthly sales, ads and "
        "returns. Check the price and demand on Amazon before you order.",
        "Fees are Amazon's 2026 US rates for standard-size items, non-peak. From 15 October "
        "to 14 January fulfilment costs a little more.",
        "Inbound placement is assumed free (Amazon-optimised split); choosing fewer "
        "warehouses adds a fee per unit.",
        *duty.notes,
    ]
    if est is not None:
        notes.append(est.notes[0])  # "an estimate, not a quote"
    return FbaEstimate(
        product=product,
        origin=duty.duty.country,
        category=category,
        size=AmazonSize(
            tier=fulfil.tier,
            label=SIZE_LABELS[fulfil.tier],
            shipping_weight_lb=fulfil.shipping_weight_lb,
            cubic_feet=round(parcel.cubic_feet, 3),
        ),
        duty=duty.duty,
        duty_stale=duty.stale,
        shipment=FbaShipment(
            container=shipped.container,
            containers=shipped.containers,
            label=shipped.label,
            volume_m3=volume,
            kg=kg,
            freight_usd=shipped.total,
            import_fees_usd=fees_entry,
            days_low=est.route.days_low if est else None,
            days_high=est.route.days_high if est else None,
            route=f"{est.route.origin_port} → {est.route.dest_port}" if est else None,
            rates_as_of=est.rates_as_of if est else None,
        ),
        costs=costs,
        landed_unit=landed,
        amazon_fees_unit=amazon,
        total_cost_unit=total,
        profit_unit=profit,
        margin=margin,
        roi=roi,
        break_even_price=break_even(data, parcel, landed.typical, storage),
        months_of_stock=round(cover, 1),
        monthly_profit=monthly,
        first_order_cash=cash,
        payback_months=payback,
        verdict=_verdict(data, margin, roi, cover),
        notes=notes,
        duty_source_url=duty.source_url,
        fees_as_of=fba_fees.FEES_AS_OF,
    )
