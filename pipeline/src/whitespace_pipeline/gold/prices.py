"""Prices from customs data: value divided by weight (USD per kg).

BACI reports value and, for most flows, quantity in metric tons. A price is only given
when enough weight is reported: tiny shipments make value/weight too noisy to compare.
"""

from __future__ import annotations

import polars as pl

MIN_PRICED_TONS = 1.0


def priced_value(year: int) -> pl.Expr:
    """Value of the flows in `year` that report a quantity (the price numerator)."""
    return (
        pl.col("value_usd")
        .filter((pl.col("year") == year) & pl.col("quantity_t").is_not_null())
        .sum()
    )


def tons(year: int) -> pl.Expr:
    return pl.col("quantity_t").filter(pl.col("year") == year).sum()


def per_kg(value: str, quantity_t: str) -> pl.Expr:
    """USD per kg, or null when less than MIN_PRICED_TONS were weighed."""
    return (
        pl.when(pl.col(quantity_t) >= MIN_PRICED_TONS)
        .then(pl.col(value) / (pl.col(quantity_t) * 1000))
        .otherwise(None)
    )
