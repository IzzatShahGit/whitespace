"""Can a seller compete on price in a market? One place for the arithmetic and wording.

Market prices are customs value ÷ weight (FOB), the same basis as a seller's cost.
"""

from __future__ import annotations

from dataclasses import dataclass

from whitespace_api.schemas.trade import Tone

COMPETITIVE = -0.10  # cost at least 10% under what the market pays
TIGHT = 0.10


@dataclass(frozen=True)
class PriceCheck:
    cost_usd_kg: float | None
    revenue_usd: float | None  # the quantity sold at the market's average price
    tone: Tone | None
    verdict: str | None


def check_price(
    *, value_usd: float, quantity_kg: float | None, market_price: float | None, market: str
) -> PriceCheck:
    cost = value_usd / quantity_kg if quantity_kg else None
    revenue = market_price * quantity_kg if market_price and quantity_kg else None
    if cost is None or not market_price:
        return PriceCheck(cost, revenue, None, None)
    gap = cost / market_price - 1
    if gap <= COMPETITIVE:
        return PriceCheck(
            cost,
            revenue,
            "positive",
            f"Your cost is {-gap:.0%} below what {market} pays on average: room to compete "
            "on price and still earn a margin.",
        )
    if gap < TIGHT:
        return PriceCheck(
            cost,
            revenue,
            "neutral",
            f"Your cost is close to what {market} pays on average: margins will be thin once "
            "freight and duties are added. Compete on quality, speed or a niche.",
        )
    return PriceCheck(
        cost,
        revenue,
        "negative",
        f"Your cost is {gap:.0%} above what {market} pays on average: you'd sell at a loss at "
        "today's prices. Look for a premium segment or a market that pays more.",
    )
