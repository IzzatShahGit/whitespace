"""Load gold tables into Postgres.

The API's Alembic migrations own the schema; this stage only replaces table contents.
Each load is one transaction: readers see the old data until the new data commits,
and a failure halfway leaves the old data untouched. COPY keeps it fast.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import polars as pl
import psycopg

from whitespace_pipeline.config import PipelineSettings
from whitespace_shared.gold import (
    COUNTRY_TABLE,
    MARKET_OPPORTUNITY_TABLE,
    MARKET_SUPPLIER_TABLE,
    PRODUCT_TABLE,
    SEA_ROUTE_TABLE,
    SUPPLIER_LANDSCAPE_TABLE,
)

log = logging.getLogger(__name__)


def libpq_url(url: str) -> str:
    """psycopg wants a plain postgresql:// URL; the shared .env uses SQLAlchemy's form."""
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql://" + url.removeprefix(prefix)
    return url


def _copy(cur: psycopg.Cursor[Any], table: str, frame: pl.DataFrame) -> None:
    cols = ", ".join(f'"{c}"' for c in frame.columns)
    cur.execute(f'TRUNCATE "{table}"')
    with cur.copy(f'COPY "{table}" ({cols}) FROM STDIN') as copy:
        rows: Iterable[tuple[Any, ...]] = frame.iter_rows()
        for row in rows:
            copy.write_row(row)


def tables(gold_dir: Path) -> dict[str, pl.DataFrame]:
    # Silver sorts current entries before historic ones, so "first" is the current name.
    countries = (
        pl.read_parquet(gold_dir / "countries.parquet")
        .unique("iso3", keep="first", maintain_order=True)
        .select(pl.col("iso3").alias("code"), pl.col("name").str.slice(0, 120))
    )
    return {
        COUNTRY_TABLE: countries,
        PRODUCT_TABLE: pl.read_parquet(gold_dir / "products.parquet").unique(
            "hs6", keep="first", maintain_order=True
        ),
        MARKET_OPPORTUNITY_TABLE: pl.read_parquet(gold_dir / "market_opportunity.parquet"),
        MARKET_SUPPLIER_TABLE: pl.read_parquet(gold_dir / "market_supplier.parquet"),
        SUPPLIER_LANDSCAPE_TABLE: pl.read_parquet(gold_dir / "supplier_landscape.parquet"),
    }


def run(settings: PipelineSettings) -> dict[str, int]:
    gold_dir = settings.gold_dir / f"V{settings.baci_version}"
    if not (gold_dir / "market_opportunity.parquet").exists():
        raise RuntimeError("Gold is missing; run `ws-pipeline gold` first")
    data = tables(gold_dir)
    routes = settings.gold_dir / "sea_routes.parquet"  # from `ws-pipeline routes`
    if routes.exists():
        data[SEA_ROUTE_TABLE] = pl.read_parquet(routes)
    with psycopg.connect(libpq_url(settings.database_url)) as conn, conn.cursor() as cur:
        for table, frame in data.items():
            _copy(cur, table, frame)
            log.info("loaded %s rows into %s", f"{frame.height:,}", table)
        cur.execute(f'ANALYZE "{MARKET_OPPORTUNITY_TABLE}"')
    # Leaving the `with` block commits; an exception rolls everything back.
    return {table: frame.height for table, frame in data.items()}
