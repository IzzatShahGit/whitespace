"""Load stage against the real test database (skipped if Postgres isn't running)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import polars as pl
import psycopg
import pytest
from sqlalchemy import create_engine, text

from whitespace_api.models import Base  # schema owned by the API's models/migrations
from whitespace_pipeline.config import PipelineSettings
from whitespace_pipeline.load import postgres
from whitespace_shared.gold import MARKET_OPPORTUNITY_TABLE

ADMIN = os.getenv(
    "TEST_DATABASE_ADMIN_DSN", "postgresql://whitespace:whitespace@localhost:5440/whitespace"
)
TEST_URL = ADMIN.rsplit("/", 1)[0] + "/whitespace_test"


@pytest.fixture
def db() -> str:
    try:
        with psycopg.connect(ADMIN, connect_timeout=3, autocommit=True) as conn:
            if not conn.execute(
                "SELECT 1 FROM pg_database WHERE datname='whitespace_test'"
            ).fetchone():
                conn.execute("CREATE DATABASE whitespace_test")
    except psycopg.OperationalError:
        pytest.skip("Postgres not reachable on :5440; run `make db`")
    engine = create_engine(TEST_URL.replace("postgresql://", "postgresql+psycopg://"))
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        Base.metadata.drop_all(conn)
        Base.metadata.create_all(conn)
    engine.dispose()
    return TEST_URL


def write_gold(root: Path, version: str, rows: int) -> None:
    out = root / "gold" / f"V{version}"
    out.mkdir(parents=True)
    pl.DataFrame(
        {"code": [586, 276], "iso3": ["PAK", "DEU"], "name": ["Pakistan", "Germany"]}
    ).write_parquet(out / "countries.parquet")
    pl.DataFrame(
        {"hs6": ["630260"], "description": ["Towels, terry, of cotton"], "hs_revision": ["HS17"]}
    ).write_parquet(out / "products.parquet")
    pl.DataFrame(
        {
            "exporter": ["PAK"] * rows,
            "market": [f"M{i:02d}" for i in range(rows)],
            "hs6": ["630260"] * rows,
            "data_year": [2024] * rows,
            "market_imports_usd": [20e6] * rows,
            "import_growth_3y": [0.26] * rows,
            "top_rival": ["CHN"] * rows,
            "top_rival_share_change": [-0.3] * rows,
            "exporter_share": [0.5] * rows,
            "exporter_rca": [12.0] * rows,
            "score": [0.8] * rows,
            "rank": list(range(1, rows + 1)),
            "data_version": ["TEST"] * rows,
        },
        schema_overrides={"data_year": pl.Int32, "rank": pl.Int32},
    ).write_parquet(out / "market_opportunity.parquet")


def test_load_replaces_tables(db: str, tmp_path: Path) -> None:
    settings = PipelineSettings(
        _env_file=None, data_dir=tmp_path, baci_version="1", database_url=db
    )  # type: ignore[call-arg]
    write_gold(tmp_path, "1", rows=5)
    assert postgres.run(settings)[MARKET_OPPORTUNITY_TABLE] == 5

    # A second load with fewer rows replaces, not appends.
    shutil.rmtree(tmp_path / "gold")
    write_gold(tmp_path, "1", rows=3)
    postgres.run(settings)
    with psycopg.connect(db) as conn:
        count = conn.execute(f"SELECT count(*) FROM {MARKET_OPPORTUNITY_TABLE}").fetchone()
        name = conn.execute("SELECT name FROM ref_country WHERE code='PAK'").fetchone()
    assert count == (3,)
    assert name == ("Pakistan",)


def test_libpq_url_strips_sqlalchemy_driver() -> None:
    assert postgres.libpq_url("postgresql+asyncpg://u:p@h:1/d") == "postgresql://u:p@h:1/d"
    assert postgres.libpq_url("postgres://u:p@h:1/d") == "postgresql://u:p@h:1/d"
