"""Product ideas for Amazon sellers, each backed by a named source.

- What sells now: Amazon's best-seller lists, captured weekly (services/bestsellers.py).
- What's growing: US imports by customs code, from the Census Bureau (a shipped file,
  whitespace_shared.us_imports), grouped into Amazon categories.
Both are read-only here; nothing is computed by a model.
"""

from __future__ import annotations

import re
from functools import cache
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.repositories import trade as trade_repo
from whitespace_api.schemas.ideas import (
    AmazonBestsellersOut,
    AmazonCategoryOut,
    BestsellerItem,
    BestsellerList,
    CategoryTrend,
    IdeasOut,
    ImportTrends,
    ProductSize,
    RisingProduct,
    StartingPoint,
)
from whitespace_api.services import bestsellers, freight, us_duties
from whitespace_api.services.fba_fees import CategoryKey
from whitespace_shared import us_imports, us_tariffs
from whitespace_shared.aliases import ALIASES
from whitespace_shared.amazon_categories import BY_KEY, CATEGORIES, AmazonCategory, category_of
from whitespace_shared.amazon_categories import fee_category as fee_for_code
from whitespace_shared.naming import everyday_name, short_product

MIN_RISING_USD_K = 20_000  # $20M a year: big enough that growth isn't one shipment
MIN_BASE_USD_K = 2_000  # and something to grow from
MIN_GROWTH = 0.05
RISING_PER_CATEGORY = 6
NAME_LENGTH = 70
_DANGLING = frozenset({"of", "and", "or", "the", "with", "for", "in", "not", "other"})


def _category(c: AmazonCategory) -> AmazonCategoryOut:
    return AmazonCategoryOut(key=c.key, label=c.label, bestsellers_url=c.bestsellers_url)


def _growth(now: int, before: int) -> float | None:
    return round(now / before - 1, 4) if before > 0 else None


def _fee(hs6: str | None, category: AmazonCategory) -> CategoryKey:
    """The code's own fee category if it sells in this Amazon category, else the
    category's (a guessed code from elsewhere mustn't change the fee)."""
    found = category_of(hs6) if hs6 else None
    fee = fee_for_code(hs6) if hs6 and found and found.key == category.key else category.fee
    return cast(CategoryKey, fee)


def display_name(hs6: str, description: str) -> str:
    """A product name to show: the everyday name when the dictionary has one ("towels"),
    else the official wording's head ("Vacuum flasks and other vacuum vessels"), or its
    detail when the head is only a material ("Glass: safety glass" -> "Safety glass")."""
    # Only an everyday name made for this exact code: one for its heading can be a
    # neighbour's ("bed linen" for table linen).
    if any(code == hs6 for codes in ALIASES.values() for code in codes):
        name = everyday_name(hs6, description)
    else:
        head = re.sub(r"\s*\([^)]*\)", "", description.partition(": ")[0]).strip()
        name = head if len(head.split()) > 2 else short_product(description)
    if len(name) > NAME_LENGTH:
        words = name[:NAME_LENGTH].rsplit(" ", 1)[0].split()
        while words and words[-1].strip(",;") in _DANGLING:
            words.pop()
        name = " ".join(words)
    name = name.strip(" ,;")
    return name[:1].upper() + name[1:]


def _name(hs6: str, products: dict[str, Any], fallback: str) -> str:
    product = products.get(hs6)
    if product is None:
        return fallback[:1].upper() + fallback[1:].lower()
    return display_name(hs6, product.description)


KG_PER_LB = 0.453592
MARKET = "USA"


async def starting_points(
    db: AsyncSession, weights: dict[str, float | None]
) -> dict[str, StartingPoint]:
    """Per code: the biggest US supplier we can price shipping from, and (given the
    product's weight in pounds) what one unit costs at its US import price."""
    routable = {c.code: c for c in await freight.origins_to(db, MARKET)}
    best: dict[str, Any] = {}
    for row in await trade_repo.suppliers_for(db, market=MARKET, codes=sorted(weights)):
        current = best.get(row.hs6)
        if row.supplier in routable and (current is None or row.share_end > current.share_end):
            best[row.hs6] = row
    out: dict[str, StartingPoint] = {}
    for hs6, row in best.items():
        per_kg = row.unit_price_usd_kg
        weight = weights.get(hs6)
        cost = round(per_kg * weight * KG_PER_LB, 2) if per_kg and weight else None
        out[hs6] = StartingPoint(
            origin=routable[row.supplier],
            share=round(row.share_end, 4),
            price_per_kg_usd=round(per_kg, 2) if per_kg else None,
            unit_cost_usd=max(cost, 0.05) if cost is not None else None,
        )
    return out


def _size(raw: dict[str, Any] | None) -> ProductSize | None:
    if not raw:
        return None
    length, width, height = raw["in"]
    return ProductSize(
        length_in=length,
        width_in=width,
        height_in=height,
        weight_lb=raw["lb"],
        packed=raw["packed"],
    )


# --- what's growing (Census) ---------------------------------------------------------


@cache
def _china_extra(hs6: str) -> float | None:
    schedule = us_tariffs.load()
    if schedule is None:
        return None
    found = us_duties.extras(
        schedule, origin="CHN", hs6=hs6, base_pct=0.0, duty_free_by_agreement=False
    )
    return round(found.total_pct, 1)


def category_trends(data: us_imports.Imports) -> list[CategoryTrend]:
    totals: dict[str, list[int]] = {}
    for series in data.series.values():
        found = category_of(series.hs6)
        if found is None:
            continue
        t = totals.setdefault(found.key, [0, 0, 0, 0, 0])
        t[0] += series.last_year
        t[1] += series.year_before
        t[2] += series.last_quarter
        t[3] += series.quarter_year_ago
        t[4] += 1
    trends = [
        CategoryTrend(
            category=_category(BY_KEY[key]),
            imports_usd=now * 1000.0,
            growth=_growth(now, before),
            recent_growth=_growth(quarter, quarter_before),
            codes=codes,
        )
        for key, (now, before, quarter, quarter_before, codes) in totals.items()
    ]
    return sorted(trends, key=lambda t: t.growth if t.growth is not None else -9, reverse=True)


def rising_series(data: us_imports.Imports) -> list[us_imports.Series]:
    """Codes still growing: up on the year and on the latest quarter, best few per category."""
    picked: dict[str, list[us_imports.Series]] = {}
    candidates = [
        s
        for s in data.series.values()
        if s.last_year >= MIN_RISING_USD_K
        and s.year_before >= MIN_BASE_USD_K
        and s.last_year / s.year_before - 1 >= MIN_GROWTH
        and s.last_quarter > s.quarter_year_ago
    ]
    for s in sorted(candidates, key=lambda s: s.last_year / s.year_before, reverse=True):
        found = category_of(s.hs6)
        if found is not None and len(picked.setdefault(found.key, [])) < RISING_PER_CATEGORY:
            picked[found.key].append(s)
    rising = [s for group in picked.values() for s in group]
    return sorted(rising, key=lambda s: s.last_year / s.year_before, reverse=True)


async def import_trends(db: AsyncSession) -> ImportTrends | None:
    data = us_imports.load()
    if data is None:
        return None
    rising = rising_series(data)
    products = await trade_repo.products_by_code(db, [s.hs6 for s in rising])
    starts = await starting_points(db, dict.fromkeys(products))
    out: list[RisingProduct] = []
    for s in rising:
        category = category_of(s.hs6)
        assert category is not None  # rising_series only keeps categorised codes
        out.append(
            RisingProduct(
                hs6=s.hs6,
                name=_name(s.hs6, products, s.desc),
                category=category.key,
                fee_category=_fee(s.hs6, category),
                in_catalog=s.hs6 in products,
                imports_usd=s.last_year * 1000.0,
                growth=round(s.last_year / s.year_before - 1, 4),
                recent_growth=_growth(s.last_quarter, s.quarter_year_ago),
                monthly_usd=[v * 1000.0 for v in s.monthly],
                china_extra_pct=_china_extra(s.hs6),
                start=starts.get(s.hs6),
            )
        )
    return ImportTrends(
        source=data.source,
        source_url=data.source_url,
        first_month=data.first_month,
        last_month=data.last_month,
        categories=category_trends(data),
        rising=out,
    )


# --- what sells now (Amazon) ---------------------------------------------------------


def _start_for(point: StartingPoint | None, size: dict[str, Any] | None) -> StartingPoint | None:
    """The code's starting point, costed at this product's own weight."""
    if point is None:
        return None
    cost = None
    if point.price_per_kg_usd and size:
        cost = max(round(point.price_per_kg_usd * size["lb"] * KG_PER_LB, 2), 0.05)
    return point.model_copy(update={"unit_cost_usd": cost})


async def amazon_lists(db: AsyncSession) -> AmazonBestsellersOut | None:
    current, previous = await bestsellers.latest(db)
    if current is None:
        return None
    moves = bestsellers.movement(current.items, previous.items if previous else None)
    codes = sorted({i["hs6"] for i in current.items if i.get("hs6")})
    products = await trade_repo.products_by_code(db, codes)
    # One code can cover products of different weights, so the cost is per product.
    origins = await starting_points(db, dict.fromkeys(products))
    lists: list[BestsellerList] = []
    for category in CATEGORIES:
        items = [i for i in current.items if i["category"] == category.key]
        if not items:
            continue
        lists.append(
            BestsellerList(
                category=_category(category),
                items=[
                    BestsellerItem(
                        rank=i["rank"],
                        name=i["name"],
                        plain_name=i.get("plain"),
                        price_usd=i.get("price"),
                        list_price_usd=i.get("list_price"),
                        stars=i.get("stars"),
                        reviews=i.get("reviews"),
                        bought=i.get("bought"),
                        brand=i.get("brand"),
                        size=_size(i.get("size")),
                        start=_start_for(origins.get(i.get("hs6") or ""), i.get("size")),
                        asin=i.get("asin"),
                        url=i["url"],
                        hs6=i.get("hs6") if i.get("hs6") in products else None,
                        product_name=(
                            _name(i["hs6"], products, "") if i.get("hs6") in products else None
                        ),
                        fee_category=_fee(i.get("hs6"), category),
                        moved=moves.get((category.key, i["rank"])),
                        is_new=(category.key, i["rank"]) in moves
                        and moves[(category.key, i["rank"])] is None,
                    )
                    for i in sorted(items, key=lambda i: i["rank"])
                ],
            )
        )
    return AmazonBestsellersOut(
        captured_at=current.captured_at,
        previous_at=previous.captured_at if previous else None,
        source=bestsellers.SOURCE,
        lists=lists,
    )


async def ideas(db: AsyncSession) -> IdeasOut:
    return IdeasOut(
        categories=[_category(c) for c in CATEGORIES],
        amazon=await amazon_lists(db),
        imports=await import_trends(db),
    )
