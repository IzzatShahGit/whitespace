"""Gold: market metrics and the v0 opportunity score (see the project doc).

For exporter country E, product p and market M, using the last 4 years (t0 .. t3):

Filters
  - market imports of p in t3 >= MIN_MARKET_IMPORTS_USD ($10M)
  - E's revealed comparative advantage in p (t3) >= MIN_RCA (1.0)
  - M != E

Signals
  g  = import growth: (imports_t3 / imports_t0) ** (1/3) - 1
  l  = share lost by the largest supplier in t0 other than E (t0 share - t3 share)
  s  = E's share of M's imports of p in t3
  m  = market size: M's imports of p in t3

Score = mean of percentile ranks of g, l, (1 - s) and m among E's passing markets for p.
Market size is in the score so a big market with steady demand isn't outranked by a
tiny one where a single shipment swung the shares (noise at small volumes).
All signals are country level: where E's country competes well, not a promise to a firm.
"""

from __future__ import annotations

import logging
from pathlib import Path

import polars as pl

from whitespace_pipeline.config import PipelineSettings
from whitespace_pipeline.gold.prices import per_kg, priced_value, tons
from whitespace_pipeline.gold.sourcing import compute_landscape
from whitespace_pipeline.io import validate_against, write_parquet_atomic
from whitespace_pipeline.silver import baci as silver
from whitespace_shared.gold import MarketOpportunity, MarketSupplier, SupplierLandscape

log = logging.getLogger(__name__)

MIN_MARKET_IMPORTS_USD = 10_000_000
MIN_RCA = 1.0
GROWTH_YEARS = 3
TOP_SUPPLIERS = 6
BUYER_MIN_IMPORTS_USD = 100_000  # products a covered country buys, for the sourcing view


def _pct(col: str) -> pl.Expr:
    """Percentile rank (0, 1] within one exporter-product group."""
    group = ["exporter", "hs6"]
    return pl.col(col).rank("average").over(group) / pl.len().over(group)


def compute(flows: pl.DataFrame, exporters: list[str], data_version: str) -> pl.DataFrame:
    t3 = int(flows["year"].max())  # type: ignore[arg-type]
    t0 = t3 - GROWTH_YEARS
    years = set(flows["year"].unique().to_list())
    if not {t0, t3} <= years:
        raise ValueError(f"Need years {t0} and {t3}, have {sorted(years)}")

    last = flows.filter(pl.col("year") == t3)
    first = flows.filter(pl.col("year") == t0)

    # Market size and growth per (market, product).
    imports = (
        flows.filter(pl.col("year").is_in([t0, t3]))
        .group_by("importer", "hs6")
        .agg(
            pl.col("value_usd").filter(pl.col("year") == t3).sum().alias("m_t3"),
            pl.col("value_usd").filter(pl.col("year") == t0).sum().alias("m_t0"),
            priced_value(t3).alias("m_pv_t3"),
            tons(t3).alias("m_q_t3"),
        )
        .filter(pl.col("m_t3") >= MIN_MARKET_IMPORTS_USD, pl.col("m_t0") > 0)
        .with_columns(
            ((pl.col("m_t3") / pl.col("m_t0")) ** (1 / GROWTH_YEARS) - 1).alias("growth"),
            per_kg("m_pv_t3", "m_q_t3").alias("market_unit_price_usd_kg"),
        )
    )

    # Revealed comparative advantage in t3: (X_Ep / X_E) / (X_wp / X_w).
    world_total = last["value_usd"].sum()
    world_by_product = last.group_by("hs6").agg(pl.col("value_usd").sum().alias("x_wp"))
    by_exporter = last.group_by("exporter").agg(pl.col("value_usd").sum().alias("x_e"))
    rca = (
        last.filter(pl.col("exporter").is_in(exporters))
        .group_by("exporter", "hs6")
        .agg(pl.col("value_usd").sum().alias("x_ep"))
        .join(by_exporter, on="exporter")
        .join(world_by_product, on="hs6")
        .with_columns(
            ((pl.col("x_ep") / pl.col("x_e")) / (pl.col("x_wp") / world_total)).alias("rca")
        )
        .filter(pl.col("rca") >= MIN_RCA)
        .select("exporter", "hs6", "rca")
    )

    candidates = rca.join(imports, on="hs6").filter(pl.col("importer") != pl.col("exporter"))

    # E's current share in each market.
    share = (
        last.select("exporter", "importer", "hs6", pl.col("value_usd").alias("x_emp"))
        .group_by("exporter", "importer", "hs6")
        .agg(pl.col("x_emp").sum())
    )

    # Top two suppliers per market in t0; the rival is the top one that isn't E.
    top2 = (
        first.group_by("importer", "hs6", "exporter")
        .agg(pl.col("value_usd").sum())
        .sort("value_usd", descending=True)
        .group_by("importer", "hs6", maintain_order=True)
        .head(2)
        .with_columns(pl.int_range(pl.len()).over("importer", "hs6").alias("pos"))
    )
    rival1 = top2.filter(pl.col("pos") == 0).select(
        "importer", "hs6", pl.col("exporter").alias("r1"), pl.col("value_usd").alias("r1_t0")
    )
    rival2 = top2.filter(pl.col("pos") == 1).select(
        "importer", "hs6", pl.col("exporter").alias("r2"), pl.col("value_usd").alias("r2_t0")
    )
    supplier_t3 = last.group_by("importer", "hs6", "exporter").agg(
        pl.col("value_usd").sum().alias("rival_t3")
    )

    scored = (
        candidates.join(share, on=["exporter", "importer", "hs6"], how="left")
        .join(rival1, on=["importer", "hs6"], how="left")
        .join(rival2, on=["importer", "hs6"], how="left")
        .with_columns(
            exporter_share=(pl.col("x_emp").fill_null(0) / pl.col("m_t3")).clip(0, 1),
            top_rival=pl.when(pl.col("r1") != pl.col("exporter"))
            .then(pl.col("r1"))
            .otherwise(pl.col("r2")),
            rival_t0=pl.when(pl.col("r1") != pl.col("exporter"))
            .then(pl.col("r1_t0"))
            .otherwise(pl.col("r2_t0")),
        )
        .join(
            supplier_t3.rename({"exporter": "top_rival"}),
            on=["importer", "hs6", "top_rival"],
            how="left",
        )
        .with_columns(
            top_rival_share=pl.when(pl.col("top_rival").is_not_null()).then(
                (pl.col("rival_t3").fill_null(0) / pl.col("m_t3")).clip(0, 1)
            ),
            top_rival_share_change=(
                pl.col("rival_t3").fill_null(0) / pl.col("m_t3")
                - pl.col("rival_t0") / pl.col("m_t0")
            ),
        )
        .with_columns(
            # Share lost by the rival: positive means room opened up. No rival -> 0.
            (-pl.col("top_rival_share_change")).fill_null(0).alias("rival_loss"),
            (1 - pl.col("exporter_share")).alias("headroom"),
        )
        .with_columns(
            ((_pct("growth") + _pct("rival_loss") + _pct("headroom") + _pct("m_t3")) / 4).alias(
                "score"
            )
        )
        .with_columns(
            pl.col("score")
            .rank("ordinal", descending=True)
            .over("exporter", "hs6")
            .cast(pl.Int32)
            .alias("rank")
        )
    )

    return scored.select(
        "exporter",
        pl.col("importer").alias("market"),
        "hs6",
        pl.lit(t3, dtype=pl.Int32).alias("data_year"),
        pl.col("m_t3").alias("market_imports_usd"),
        pl.col("growth").alias("import_growth_3y"),
        "top_rival",
        "top_rival_share_change",
        "top_rival_share",
        "market_unit_price_usd_kg",
        "exporter_share",
        pl.col("rca").alias("exporter_rca"),
        "score",
        "rank",
        pl.lit(data_version).alias("data_version"),
    ).sort("exporter", "hs6", "rank")


def ranked_pairs(opportunities: pl.DataFrame) -> pl.DataFrame:
    """(importer, hs6) for every ranked market."""
    return opportunities.select(pl.col("market").alias("importer"), "hs6").unique()


def buyer_pairs(flows: pl.DataFrame, buyers: list[str], t3: int) -> pl.DataFrame:
    """(importer, hs6) for products the covered countries buy (for the sourcing view)."""
    return (
        flows.filter(pl.col("year") == t3, pl.col("importer").is_in(buyers))
        .group_by("importer", "hs6")
        .agg(pl.col("value_usd").sum())
        .filter(pl.col("value_usd") >= BUYER_MIN_IMPORTS_USD)
        .select("importer", "hs6")
    )


def compute_suppliers(
    flows: pl.DataFrame, pairs: pl.DataFrame, t3: int, top_n: int = TOP_SUPPLIERS
) -> pl.DataFrame:
    """The largest suppliers (last year) of each (market, product) in `pairs`, with
    start and end shares and price per kg."""
    t0 = t3 - GROWTH_YEARS
    window = flows.filter(pl.col("year").is_in([t0, t3])).join(
        pairs.unique(), on=["importer", "hs6"], how="semi"
    )
    by_supplier = window.group_by("importer", "hs6", "exporter").agg(
        pl.col("value_usd").filter(pl.col("year") == t0).sum().alias("v_t0"),
        pl.col("value_usd").filter(pl.col("year") == t3).sum().alias("v_t3"),
        priced_value(t3).alias("pv_t3"),
        tons(t3).alias("q_t3"),
    )
    return (
        by_supplier.with_columns(
            share_start=pl.col("v_t0") / pl.col("v_t0").sum().over("importer", "hs6"),
            share_end=pl.col("v_t3") / pl.col("v_t3").sum().over("importer", "hs6"),
            unit_price_usd_kg=per_kg("pv_t3", "q_t3"),
        )
        .filter(pl.col("v_t3") > 0)
        .sort("v_t3", descending=True)
        .group_by("importer", "hs6", maintain_order=True)
        .head(top_n)
        .select(
            pl.col("importer").alias("market"),
            "hs6",
            pl.col("exporter").alias("supplier"),
            pl.col("v_t3").alias("value_usd"),
            pl.col("share_start").fill_nan(0).fill_null(0).clip(0, 1),
            pl.col("share_end").clip(0, 1),
            "unit_price_usd_kg",
        )
        .sort("market", "hs6", "value_usd", descending=[False, False, True])
    )


def run(settings: PipelineSettings) -> Path:
    src = silver.silver_root(settings)
    flows = pl.read_parquet(src / "flows.parquet")
    version = f"BACI-{settings.baci_hs_revision}-V{settings.baci_version}"
    gold = compute(flows, settings.exporters, version)
    validate_against(gold, MarketOpportunity)
    t3 = int(gold["data_year"].max())  # type: ignore[arg-type]
    pairs = pl.concat([ranked_pairs(gold), buyer_pairs(flows, settings.exporters, t3)])
    suppliers = compute_suppliers(flows, pairs, t3)
    validate_against(suppliers, MarketSupplier)
    landscape = compute_landscape(flows, t3, GROWTH_YEARS)
    validate_against(landscape, SupplierLandscape)

    out = settings.gold_dir / f"V{settings.baci_version}"
    write_parquet_atomic(gold, out / "market_opportunity.parquet")
    write_parquet_atomic(suppliers, out / "market_supplier.parquet")
    write_parquet_atomic(landscape, out / "supplier_landscape.parquet")
    for name in ("countries", "products"):
        write_parquet_atomic(pl.read_parquet(src / f"{name}.parquet"), out / f"{name}.parquet")
    log.info(
        "gold: %s ranked markets for %s exporters, %s products; %s supplier rows; "
        "%s landscape rows",
        f"{gold.height:,}",
        gold["exporter"].n_unique(),
        gold["hs6"].n_unique(),
        f"{suppliers.height:,}",
        f"{landscape.height:,}",
    )
    return out
