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
    exporters: list[str] = ["PAK", "BGD", "VNM", "IND", "TUR", "EGY", "MAR", "KEN", "LKA", "ETH"]

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
