"""Amazon US selling fees for FBA (Fulfilment by Amazon). Pure: no I/O.

Rates as Amazon published them for 2026 (effective 15 January 2026), with the 3.5% fuel
and logistics surcharge on fulfilment fees from 17 April 2026. Sources: Amazon's
pricing page (referral fees, plans) and its 2026 fee update; the per-band fulfilment
table cross-checked in two independent seller-tool references. Review with each
Amazon fee change (the next is announced for 15 January 2027): bump `FEES_AS_OF`.

Covers standard-size items (small and large standard, up to 20 lb), which is where most
first products sit. Bulky items have their own tiers and are refused with a message.
Peak-season (15 Oct to 14 Jan) fulfilment rates are higher and are mentioned, not used.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

FEES_AS_OF = "2026-01-15"
FEES_SOURCE = "https://sell.amazon.com/pricing"
FUEL_SURCHARGE = 0.035  # on the fulfilment fee, since 2026-04-17
PROFESSIONAL_PLAN_USD = 39.99  # a month
DIM_DIVISOR = 139  # cubic inches per pound
DIM_MIN_SIDE_IN = 2.0  # width and height count as at least 2 in for dimensional weight
CUBIC_IN_PER_FT = 1728

# Monthly storage, standard size, per cubic foot: January-September, October-December.
STORAGE_OFF_PEAK, STORAGE_PEAK = 0.78, 2.40
STORAGE_AVG = (STORAGE_OFF_PEAK * 9 + STORAGE_PEAK * 3) / 12
AGED_AFTER_MONTHS = 6  # stock older than 181 days pays an aged-inventory surcharge

SizeTier = Literal["small_standard", "large_standard"]
PriceBand = Literal["under_10", "10_to_50", "over_50"]
BAND_INDEX: dict[PriceBand, int] = {"under_10": 0, "10_to_50": 1, "over_50": 2}

# Fulfilment fee per unit, non-peak: (max shipping weight in oz, fee by price band).
SMALL_STANDARD: tuple[tuple[float, tuple[float, float, float]], ...] = (
    (2, (2.43, 3.32, 3.58)),
    (4, (2.49, 3.42, 3.68)),
    (6, (2.56, 3.45, 3.71)),
    (8, (2.66, 3.54, 3.80)),
    (10, (2.77, 3.68, 3.94)),
    (12, (2.82, 3.78, 4.04)),
    (14, (2.92, 3.91, 4.17)),
    (16, (2.95, 3.96, 4.22)),
)
LARGE_STANDARD: tuple[tuple[float, tuple[float, float, float]], ...] = (
    (4, (2.91, 3.73, 3.99)),
    (8, (3.13, 3.95, 4.21)),
    (12, (3.38, 4.20, 4.46)),
    (16, (3.78, 4.60, 4.86)),
    (20, (4.22, 5.04, 5.30)),
    (24, (4.60, 5.42, 5.68)),
    (28, (4.75, 5.57, 5.83)),
    (32, (5.00, 5.82, 6.08)),
    (36, (5.10, 5.92, 6.18)),
    (40, (5.28, 6.10, 6.36)),
    (44, (5.44, 6.26, 6.52)),
    (48, (5.85, 6.67, 6.93)),
)
# Over 3 lb (48 oz) up to 20 lb: the base plus this much per 4 oz (or part) above 3 lb.
LARGE_OVER_3LB_BASE = (6.15, 6.97, 7.23)
LARGE_PER_4OZ = 0.08

# Size limits in inches (longest, median, shortest) and max weight in oz.
SMALL_LIMITS = ((15.0, 12.0, 0.75), 16.0)
LARGE_LIMITS = ((18.0, 14.0, 8.0), 20 * 16.0)


@dataclass(frozen=True)
class Tier:
    """A referral-fee step: `rate` applies up to `up_to` dollars (None: no limit)."""

    rate: float
    up_to: float | None = None


@dataclass(frozen=True)
class Category:
    label: str
    tiers: tuple[Tier, ...]
    portion: bool  # True: each rate applies to its slice of the price; False: whole price
    minimum: float = 0.30


CATEGORIES: dict[str, Category] = {
    "home_kitchen": Category("Home & Kitchen", (Tier(0.15),), portion=False),
    "beauty_health": Category(
        "Beauty, Health & Personal Care", (Tier(0.08, 10), Tier(0.15)), portion=False
    ),
    "baby": Category("Baby", (Tier(0.08, 10), Tier(0.15)), portion=False),
    "clothing": Category(
        "Clothing & Accessories", (Tier(0.05, 15), Tier(0.10, 20), Tier(0.17)), portion=False
    ),
    "footwear": Category("Shoes", (Tier(0.15),), portion=False),
    "luggage": Category("Backpacks, Handbags & Luggage", (Tier(0.15),), portion=False),
    "sports": Category("Sports & Outdoors", (Tier(0.15),), portion=False),
    "toys": Category("Toys & Games", (Tier(0.15),), portion=False),
    "pet": Category("Pet Supplies", (Tier(0.15),), portion=False),
    "grocery": Category(
        "Grocery & Gourmet", (Tier(0.08, 15), Tier(0.15)), portion=False, minimum=0.0
    ),
    "electronics_accessories": Category(
        "Electronics Accessories", (Tier(0.15, 100), Tier(0.08)), portion=True
    ),
    "consumer_electronics": Category("Consumer Electronics", (Tier(0.08),), portion=False),
    "furniture": Category("Furniture", (Tier(0.15, 200), Tier(0.10)), portion=True),
    "jewelry": Category("Jewelry", (Tier(0.20, 250), Tier(0.05)), portion=True),
    "other": Category("Everything else", (Tier(0.15),), portion=False),
}
CategoryKey = Literal[
    "home_kitchen", "beauty_health", "baby", "clothing", "footwear", "luggage", "sports",
    "toys", "pet", "grocery", "electronics_accessories", "consumer_electronics", "furniture",
    "jewelry", "other",
]  # fmt: skip


class NotSupportedError(Exception):
    """An item this model doesn't price (e.g. bulky). The message is safe to show."""


@dataclass(frozen=True)
class Parcel:
    """One sellable unit as packed for Amazon: inches and pounds."""

    length_in: float
    width_in: float
    height_in: float
    weight_lb: float

    @property
    def sides(self) -> tuple[float, float, float]:
        longest, median, shortest = sorted((self.length_in, self.width_in, self.height_in))[::-1]
        return longest, median, shortest

    @property
    def cubic_feet(self) -> float:
        return self.length_in * self.width_in * self.height_in / CUBIC_IN_PER_FT

    @property
    def dim_weight_lb(self) -> float:
        longest, median, shortest = self.sides
        return longest * max(median, DIM_MIN_SIDE_IN) * max(shortest, DIM_MIN_SIDE_IN) / DIM_DIVISOR


@dataclass(frozen=True)
class Fulfilment:
    tier: SizeTier
    shipping_weight_lb: float  # what the fee is charged on
    fee: float  # before the fuel surcharge
    surcharge: float

    @property
    def total(self) -> float:
        return round(self.fee + self.surcharge, 2)


def _fits(sides: tuple[float, float, float], limits: tuple[float, float, float]) -> bool:
    return all(side <= limit for side, limit in zip(sides, limits, strict=True))


def size_tier(parcel: Parcel) -> SizeTier:
    (small_sides, small_oz), (large_sides, large_oz) = SMALL_LIMITS, LARGE_LIMITS
    if _fits(parcel.sides, small_sides) and parcel.weight_lb * 16 <= small_oz:
        return "small_standard"
    shipping_oz = max(parcel.weight_lb, parcel.dim_weight_lb) * 16
    if _fits(parcel.sides, large_sides) and shipping_oz <= large_oz:
        return "large_standard"
    raise NotSupportedError(
        "This item is bulky by Amazon's size rules (over 18 x 14 x 8 in or 20 lb). Bulky "
        "items have their own fees, which this calculator doesn't cover yet: use Amazon's "
        "Revenue Calculator for it."
    )


def price_band(price: float) -> PriceBand:
    if price < 10:
        return "under_10"
    return "10_to_50" if price <= 50 else "over_50"


def fulfilment(parcel: Parcel, price: float) -> Fulfilment:
    """The per-unit FBA fee for a standard-size item at this price."""
    tier = size_tier(parcel)
    band = BAND_INDEX[price_band(price)]
    if tier == "small_standard":
        weight = parcel.weight_lb  # small standard is charged on unit weight
        table = SMALL_STANDARD
    else:
        weight = max(parcel.weight_lb, parcel.dim_weight_lb)
        table = LARGE_STANDARD
    ounces = weight * 16
    fee = next((fees[band] for limit, fees in table if ounces <= limit + 1e-9), None)
    if fee is None:  # large standard over 3 lb
        extra_steps = math.ceil((ounces - 48) / 4 - 1e-9)
        fee = LARGE_OVER_3LB_BASE[band] + LARGE_PER_4OZ * extra_steps
    fee = round(fee, 2)
    return Fulfilment(
        tier=tier,
        shipping_weight_lb=round(weight, 3),
        fee=fee,
        surcharge=round(fee * FUEL_SURCHARGE, 2),
    )


def referral(category: str, price: float) -> float:
    """Amazon's referral fee on one sale: the category's rate(s), at least its minimum."""
    found = CATEGORIES.get(category)
    if found is None:
        raise NotSupportedError(f"Unknown category {category!r}")
    if found.portion:
        fee, floor = 0.0, 0.0
        for tier in found.tiers:
            top = price if tier.up_to is None else min(price, tier.up_to)
            if top > floor:
                fee += (top - floor) * tier.rate
            if tier.up_to is None or price <= tier.up_to:
                break
            floor = tier.up_to
    else:
        rate = next(t.rate for t in found.tiers if t.up_to is None or price <= t.up_to)
        fee = price * rate
    return round(max(fee, found.minimum), 2)


def storage_per_unit(parcel: Parcel, months_held: float) -> float:
    """Storage for one unit over the months it waits, at the year's average rate."""
    return round(parcel.cubic_feet * STORAGE_AVG * months_held, 2)
