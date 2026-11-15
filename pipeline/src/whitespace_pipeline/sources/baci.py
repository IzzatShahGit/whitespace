"""CEPII BACI: bilateral trade flows, about 200 countries x 5,000 products a year.

Licence: Etalab Open Licence 2.0. Any use is allowed, provided CEPII is credited.

The release is one zip (~800 MB for HS17) holding a CSV per year plus code lists:
    BACI_HS17_Y{year}_V{version}.csv   columns t,i,j,k,v,q
    product_codes_HS17_V{version}.csv  code,description
    country_codes_V{version}.csv       country_code,country_name,country_iso2,country_iso3
t = year, i = exporter, j = importer (numeric country codes), k = HS6 product,
v = value in thousands of current USD, q = quantity in metric tons.
"""

from __future__ import annotations

import json
import logging
import re
import zipfile
from collections.abc import Callable
from pathlib import Path

import httpx
import polars as pl

from whitespace_pipeline.config import PipelineSettings

log = logging.getLogger(__name__)

# Bronze keeps values exactly as published; only the file format changes (CSV -> Parquet).
# Codes are read as text so leading zeros survive ("080810", not 80810).
FLOW_SCHEMA = pl.Schema(
    {"t": pl.Int16, "i": pl.Int32, "j": pl.Int32, "k": pl.Utf8, "v": pl.Float64, "q": pl.Float64}
)
PRODUCT_SCHEMA = pl.Schema({"code": pl.Utf8, "description": pl.Utf8})
COUNTRY_SCHEMA = pl.Schema(
    {
        "country_code": pl.Int32,
        "country_name": pl.Utf8,
        "country_iso2": pl.Utf8,
        "country_iso3": pl.Utf8,
    }
)

ProgressFn = Callable[[int, int], None]


class BaciError(RuntimeError):
    pass


def zip_name(settings: PipelineSettings) -> str:
    return f"BACI_{settings.baci_hs_revision}_V{settings.baci_version}.zip"


def bronze_root(settings: PipelineSettings) -> Path:
    return settings.bronze_dir / "baci" / settings.baci_hs_revision / f"V{settings.baci_version}"


def download(
    settings: PipelineSettings,
    client: httpx.Client | None = None,
    progress: ProgressFn | None = None,
) -> Path:
    """Download the release zip, resuming a partial download. Idempotent."""
    url = f"{settings.baci_base_url}/{zip_name(settings)}"
    target = settings.bronze_dir / "baci" / zip_name(settings)
    partial = target.with_suffix(".zip.part")
    target.parent.mkdir(parents=True, exist_ok=True)

    own_client = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(60, read=300), follow_redirects=True)
    try:
        expected = int(client.head(url).headers["content-length"])
        if target.exists() and target.stat().st_size == expected:
            log.info("BACI zip already downloaded: %s", target)
            return target

        done = partial.stat().st_size if partial.exists() else 0
        headers = {"Range": f"bytes={done}-"} if done else {}
        with client.stream("GET", url, headers=headers) as response:
            if response.status_code == 200:  # server ignored the range: start over
                done = 0
            elif response.status_code != 206:
                raise BaciError(f"Download failed: HTTP {response.status_code} for {url}")
            with partial.open("ab" if done else "wb") as out:
                for chunk in response.iter_bytes(chunk_size=1 << 20):
                    out.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, expected)

        if partial.stat().st_size != expected:
            raise BaciError(
                f"Incomplete download: {partial.stat().st_size} of {expected} bytes "
                "(run again to resume)"
            )
        partial.rename(target)
        return target
    finally:
        if own_client:
            client.close()


def available_years(archive: zipfile.ZipFile, settings: PipelineSettings) -> list[int]:
    pattern = re.compile(
        rf"^BACI_{settings.baci_hs_revision}_Y(\d{{4}})_V{settings.baci_version}\.csv$"
    )
    return sorted(int(m.group(1)) for n in archive.namelist() if (m := pattern.match(n)))


def _csv_to_parquet(archive: zipfile.ZipFile, member: str, schema: pl.Schema, out: Path) -> int:
    with archive.open(member) as handle:
        frame = pl.read_csv(
            handle.read(),
            schema_overrides=schema,
            null_values=["NA", ""],
            encoding="utf8-lossy",
        )
    if frame.columns != schema.names():
        raise BaciError(f"{member}: unexpected columns {frame.columns}")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".parquet.tmp")
    frame.write_parquet(tmp, compression="zstd")
    tmp.rename(out)  # atomic: a crash never leaves a half-written file behind
    return frame.height


def extract(zip_path: Path, settings: PipelineSettings, force: bool = False) -> list[int]:
    """Convert the last N years plus code lists to Parquet. Returns the years written."""
    root = bronze_root(settings)
    v = settings.baci_version
    with zipfile.ZipFile(zip_path) as archive:
        years = available_years(archive, settings)
        if len(years) < settings.baci_years:
            raise BaciError(f"Need {settings.baci_years} years, release has {years}")
        wanted = years[-settings.baci_years :]

        for year in wanted:
            out = root / "flows" / f"year={year}" / "part-0.parquet"
            if out.exists() and not force:
                log.info("BACI %s already in bronze", year)
                continue
            rows = _csv_to_parquet(
                archive, f"BACI_{settings.baci_hs_revision}_Y{year}_V{v}.csv", FLOW_SCHEMA, out
            )
            log.info("BACI %s: %s rows", year, f"{rows:,}")

        _csv_to_parquet(
            archive,
            f"product_codes_{settings.baci_hs_revision}_V{v}.csv",
            PRODUCT_SCHEMA,
            root / "products.parquet",
        )
        _csv_to_parquet(
            archive, f"country_codes_V{v}.csv", COUNTRY_SCHEMA, root / "countries.parquet"
        )
    return wanted


def _manifest(settings: PipelineSettings) -> Path:
    return bronze_root(settings) / "_manifest.json"


def bronze_years(settings: PipelineSettings) -> list[int] | None:
    """Years already in bronze for this release, or None if bronze is incomplete."""
    path = _manifest(settings)
    if not path.exists():
        return None
    years: list[int] = json.loads(path.read_text())["years"]
    return years


def run(
    settings: PipelineSettings, force: bool = False, progress: ProgressFn | None = None
) -> list[int]:
    """Bronze stage for BACI: download, convert, and (by default) delete the zip.

    Re-running is cheap: a finished release is recorded in a manifest and skipped.
    """
    if not force and (years := bronze_years(settings)) is not None:
        log.info("BACI V%s already in bronze (%s)", settings.baci_version, years)
        return years
    zip_path = download(settings, progress=progress)
    years = extract(zip_path, settings, force=force)
    _manifest(settings).write_text(
        json.dumps({"source": zip_name(settings), "years": years}, indent=2)
    )
    if not settings.keep_raw_zip:
        zip_path.unlink()
        log.info("Deleted %s to save disk (set KEEP_RAW_ZIP=true to keep it)", zip_path.name)
    return years
