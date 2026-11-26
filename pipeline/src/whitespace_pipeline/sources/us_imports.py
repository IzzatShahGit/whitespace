"""Monthly US imports of consumer goods, for hot Amazon categories and rising products.

Source: US Census Bureau international trade API (general imports, all countries, by
HS6), the official customs statistics, published about five weeks after each month.
One request returns every product for one month, so 24 months is 24 small requests.

Only codes in an Amazon category (whitespace_shared.amazon_categories) are kept, with
their last 24 monthly values. The result is a reference file shipped with the code,
like the US tariff table: nothing goes into the database.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx

from whitespace_pipeline.config import PipelineSettings
from whitespace_shared.amazon_categories import category_of
from whitespace_shared.us_imports import DATA_FILE, MONTHS

log = logging.getLogger(__name__)

SOURCE_URL = "https://api.census.gov/data/timeseries/intltrade/imports/hs"
SOURCE_NAME = "US Census Bureau, international trade (general imports)"
MIN_LAST_YEAR_USD = 5_000_000  # smaller lines are too thin to call a trend
MIN_ROWS = 200  # fewer kept codes means the response changed shape
REFETCH_RECENT = 3  # the newest months get revised, so they're always fetched again
TIMEOUT = httpx.Timeout(90.0, connect=10.0)


class SourceError(RuntimeError):
    """The Census API didn't answer as expected."""


def _month(index: int) -> str:
    return f"{index // 12}-{index % 12 + 1:02d}"


def _index(month: str) -> int:
    year, mon = month.split("-")
    return int(year) * 12 + int(mon) - 1


def parse(rows: list[list[str]]) -> dict[str, tuple[int, str]]:
    """Census rows -> {hs6: (value in USD, short description)}."""
    if not rows:
        return {}
    header = rows[0]
    try:
        fields = ("I_COMMODITY", "I_COMMODITY_SDESC", "GEN_VAL_MO")
        code, desc, value = (header.index(f) for f in fields)
    except ValueError as exc:
        raise SourceError(f"unexpected columns: {header}") from exc
    out: dict[str, tuple[int, str]] = {}
    for row in rows[1:]:
        hs6 = row[code]
        if len(hs6) == 6 and hs6.isdigit():
            out[hs6] = (int(row[value] or 0), row[desc].strip())
    return out


def _fetch(client: httpx.Client, key: str, month: str) -> list[list[str]] | None:
    response = client.get(
        SOURCE_URL,
        params={
            "get": "I_COMMODITY,I_COMMODITY_SDESC,GEN_VAL_MO",
            "COMM_LVL": "HS6",
            "CTY_CODE": "-",  # total for all countries
            "time": month,
            "key": key,
        },
        timeout=TIMEOUT,
    )
    if response.status_code == 204:  # not published yet
        return None
    response.raise_for_status()
    rows: list[list[str]] = response.json()
    return rows


def _month_rows(
    settings: PipelineSettings, client: httpx.Client, key: str, month: str, *, recent: bool
) -> list[list[str]] | None:
    """One month, from the bronze copy unless it's recent enough to have been revised."""
    path = settings.bronze_dir / "us_imports" / f"{month}.json"
    if path.exists() and not recent:
        rows: list[list[str]] = json.loads(path.read_text())
        return rows
    fetched = _fetch(client, key, month)
    if fetched is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(fetched))
    return fetched


def latest_month(client: httpx.Client, key: str, today: date) -> str:
    """The newest month the Census has published (it lags by five to eight weeks)."""
    current = today.year * 12 + today.month - 1
    for back in range(1, 5):
        month = _month(current - back)
        response = client.get(
            SOURCE_URL,
            params={
                "get": "GEN_VAL_MO",
                "I_COMMODITY": "630260",
                "COMM_LVL": "HS6",
                "CTY_CODE": "-",
                "time": month,
                "key": key,
            },
            timeout=TIMEOUT,
        )
        if response.status_code == 200:
            return month
        if response.status_code != 204:
            response.raise_for_status()
    raise SourceError("no month published in the last four")


def build(months: dict[str, dict[str, tuple[int, str]]], *, built: datetime) -> dict[str, Any]:
    """Keep consumer codes with enough trade; values in thousands of USD, oldest first."""
    order = sorted(months, key=_index)
    if len(order) != MONTHS:
        raise SourceError(f"expected {MONTHS} months, got {len(order)}")
    names: dict[str, str] = {}
    for month in order:
        for hs6, (_, desc) in months[month].items():
            names[hs6] = desc
    rows = []
    for hs6 in sorted(names):
        if category_of(hs6) is None:
            continue
        values = [months[m].get(hs6, (0, ""))[0] for m in order]
        if sum(values[-12:]) < MIN_LAST_YEAR_USD:
            continue
        rows.append({"hs6": hs6, "desc": names[hs6], "m": [round(v / 1000) for v in values]})
    if len(rows) < MIN_ROWS:
        raise SourceError(f"only {len(rows)} consumer codes kept; expected at least {MIN_ROWS}")
    return {
        "source": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "first_month": order[0],
        "last_month": order[-1],
        "built": built.date().isoformat(),
        "unit": "USD thousands",
        "rows": rows,
    }


def run(settings: PipelineSettings, target: Path = DATA_FILE) -> Path:
    """Fetch the last 24 published months and write the reference file atomically."""
    if not settings.census_api_key:
        raise SourceError("CENSUS_API_KEY is not set (free: api.census.gov/data/key_signup.html)")
    key = settings.census_api_key
    with httpx.Client(headers={"User-Agent": "whitespace-pipeline"}) as client:
        last = _index(latest_month(client, key, datetime.now(UTC).date()))
        months: dict[str, dict[str, tuple[int, str]]] = {}
        for i in range(last - MONTHS + 1, last + 1):
            month = _month(i)
            rows = _month_rows(settings, client, key, month, recent=last - i < REFETCH_RECENT)
            if rows is None:
                raise SourceError(f"{month} isn't published")
            months[month] = parse(rows)
            log.info("US imports %s: %d codes", month, len(months[month]))
    content = build(months, built=datetime.now(UTC))
    partial = target.with_suffix(".part")
    partial.write_text(json.dumps(content, separators=(",", ":")))
    partial.replace(target)
    log.info(
        "US imports %s to %s: %d consumer codes kept",
        content["first_month"],
        content["last_month"],
        len(content["rows"]),
    )
    return target
