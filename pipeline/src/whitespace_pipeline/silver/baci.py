"""Silver: BACI flows cleaned into analysis-ready form.

Changes from bronze:
- numeric country codes -> ISO 3166 alpha-3 (exporter, importer)
- product codes zero-padded to six digits
- value in USD (bronze is thousands of USD); quantity kept in metric tons
- zero or missing values dropped

BACI already reconciles what exporters and importers report into one figure per
flow, so no mirror-data step is needed here.
"""

from __future__ import annotations

import logging
from pathlib import Path

import polars as pl

from whitespace_pipeline.config import PipelineSettings
from whitespace_pipeline.sources import baci as source

log = logging.getLogger(__name__)

FLOWS_SCHEMA = pl.Schema(
    {
        "year": pl.Int16,
        "exporter": pl.Utf8,
        "importer": pl.Utf8,
        "hs6": pl.Utf8,
        "value_usd": pl.Float64,
        "quantity_t": pl.Float64,
    }
)


def silver_root(settings: PipelineSettings) -> Path:
    return settings.silver_dir / "baci" / settings.baci_hs_revision / f"V{settings.baci_version}"


def countries(bronze: Path) -> pl.DataFrame:
    return (
        pl.read_parquet(bronze / "countries.parquet")
        .select(
            pl.col("country_code").alias("code"),
            pl.col("country_iso3").str.strip_chars().str.to_uppercase().alias("iso3"),
            pl.col("country_name").str.strip_chars().alias("name"),
        )
        .filter(pl.col("iso3").str.len_chars() == 3)
        .unique("code")
    )


def products(bronze: Path, hs_revision: str) -> pl.DataFrame:
    return pl.read_parquet(bronze / "products.parquet").select(
        pl.col("code").str.strip_chars().str.zfill(6).alias("hs6"),
        pl.col("description").str.strip_chars(),
        pl.lit(hs_revision).alias("hs_revision"),
    )


def clean_flows(raw: pl.LazyFrame, country_codes: pl.DataFrame) -> pl.LazyFrame:
    iso = country_codes.lazy().select("code", "iso3")
    return (
        raw.filter(pl.col("v") > 0)
        .join(iso.rename({"code": "i", "iso3": "exporter"}), on="i", how="inner")
        .join(iso.rename({"code": "j", "iso3": "importer"}), on="j", how="inner")
        .filter(pl.col("exporter") != pl.col("importer"))
        .select(
            pl.col("t").alias("year"),
            "exporter",
            "importer",
            pl.col("k").str.strip_chars().str.zfill(6).alias("hs6"),
            (pl.col("v") * 1000).alias("value_usd"),
            pl.col("q").alias("quantity_t"),
        )
    )


def run(settings: PipelineSettings) -> Path:
    bronze = source.bronze_root(settings)
    if source.bronze_years(settings) is None:
        raise RuntimeError("Bronze is missing; run `ws-pipeline bronze` first")
    out = silver_root(settings)
    out.mkdir(parents=True, exist_ok=True)

    country_codes = countries(bronze)
    country_codes.write_parquet(out / "countries.parquet")
    products(bronze, settings.baci_hs_revision).write_parquet(out / "products.parquet")

    raw = pl.scan_parquet(bronze / "flows" / "year=*" / "part-0.parquet")
    flows = clean_flows(raw, country_codes).collect()
    if flows.schema != FLOWS_SCHEMA:
        raise RuntimeError(f"Silver flows schema drifted: {flows.schema}")
    tmp = out / "flows.parquet.tmp"
    flows.write_parquet(tmp, compression="zstd")
    tmp.rename(out / "flows.parquet")
    log.info("silver: %s flows, %s countries", f"{flows.height:,}", country_codes.height)
    return out
