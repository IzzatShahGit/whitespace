"""File helpers shared by every stage."""

from __future__ import annotations

from pathlib import Path

import polars as pl
from pydantic import BaseModel


def write_parquet_atomic(frame: pl.DataFrame, path: Path) -> Path:
    """Write via a temp file and rename, so a crash never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    frame.write_parquet(tmp, compression="zstd")
    tmp.rename(path)
    return path


def validate_against(frame: pl.DataFrame, contract: type[BaseModel], sample: int = 2000) -> None:
    """Columns must match the shared contract exactly; a sample of rows must validate."""
    expected = list(contract.model_fields)
    if frame.columns != expected:
        raise ValueError(f"{contract.__name__}: columns {frame.columns} != contract {expected}")
    for row in frame.sample(min(sample, frame.height), seed=0).iter_rows(named=True):
        contract(**row)
