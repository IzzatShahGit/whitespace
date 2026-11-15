"""Gold for buyers: who supplies each product to the world, at what price.

For every product, the largest exporting countries (last year) with their exports,
growth, share of world exports, how many markets they serve (a reliability signal: a
supplier trusted by many markets), and their average price per kg.
"""

from __future__ import annotations

import polars as pl

from whitespace_pipeline.gold.prices import per_kg, priced_value, tons

TOP_SOURCES = 15
SERVED_MIN_USD = 100_000  # a market "buys from" a supplier above this, per year


def compute_landscape(flows: pl.DataFrame, t3: int, growth_years: int) -> pl.DataFrame:
    t0 = t3 - growth_years
    window = flows.filter(pl.col("year").is_in([t0, t3]))
    by_supplier = window.group_by("hs6", "exporter").agg(
        pl.col("value_usd").filter(pl.col("year") == t3).sum().alias("x_t3"),
        pl.col("value_usd").filter(pl.col("year") == t0).sum().alias("x_t0"),
        priced_value(t3).alias("pv_t3"),
        tons(t3).alias("q_t3"),
        ((pl.col("year") == t3) & (pl.col("value_usd") >= SERVED_MIN_USD))
        .sum()
        .alias("markets_served"),
    )
    return (
        by_supplier.filter(pl.col("x_t3") > 0)
        .with_columns(
            world_share=(pl.col("x_t3") / pl.col("x_t3").sum().over("hs6")).clip(0, 1),
            exports_growth_3y=pl.when(pl.col("x_t0") > 0).then(
                (pl.col("x_t3") / pl.col("x_t0")) ** (1 / growth_years) - 1
            ),
            unit_price_usd_kg=per_kg("pv_t3", "q_t3"),
            rank=pl.col("x_t3").rank("ordinal", descending=True).over("hs6").cast(pl.Int32),
        )
        .filter(pl.col("rank") <= TOP_SOURCES)
        .select(
            "hs6",
            pl.col("exporter").alias("supplier"),
            "rank",
            pl.col("x_t3").alias("exports_usd"),
            "exports_growth_3y",
            "world_share",
            pl.col("markets_served").cast(pl.Int32),
            "unit_price_usd_kg",
        )
        .sort("hs6", "rank")
    )
