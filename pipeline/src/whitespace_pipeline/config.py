"""Pipeline settings, read from environment variables (or a .env file)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class PipelineSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    data_dir: Path = REPO_ROOT / "data"
    # Sync driver for bulk loads; same database as the API.
    database_url: str = "postgresql+psycopg://whitespace:whitespace@localhost:5440/whitespace"

    # v0 scope (see project doc): HS 2017 edition, last four years.
    baci_hs_revision: str = "HS17"
    # Release id (YYYYMM). 202601 covers 2017-2024. Bump when CEPII publishes a new one.
    baci_version: str = "202601"
    baci_base_url: str = "https://www.cepii.fr/DATA_DOWNLOAD/baci/data"
    baci_years: int = 4  # the minimum for 3-year growth
    keep_raw_zip: bool = False  # delete the ~800 MB zip once converted, to save disk
    # Emerging-market exporters we rank markets for. Each adds ~4-5 MB to Postgres; the
    # whole database must stay well under Neon's free 512 MB (~250 MB with this list).
    exporters: list[str] = [
        # South Asia
        "PAK", "BGD", "IND", "LKA", "NPL",
        # South-East Asia
        "VNM", "IDN", "THA", "PHL", "MYS", "KHM",
        # Middle East, Central Asia and North Africa
        "TUR", "EGY", "MAR", "TUN", "UZB",
        # Sub-Saharan Africa
        "KEN", "ETH", "NGA", "GHA", "ZAF",
        # Latin America
        "MEX", "BRA", "COL",
    ]  # fmt: skip

    @property
    def bronze_dir(self) -> Path:
        return self.data_dir / "bronze"

    @property
    def silver_dir(self) -> Path:
        return self.data_dir / "silver"

    @property
    def gold_dir(self) -> Path:
        return self.data_dir / "gold"


@lru_cache
def get_settings() -> PipelineSettings:
    return PipelineSettings()
