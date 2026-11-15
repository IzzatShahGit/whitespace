"""Monthly imports by supplier for one product into one market.

Two free sources, normalised to one shape (`MonthlyImports`):
- Eurostat Comext (dataset DS-045409): the 27 EU members, values in EUR, no key.
- US Census Bureau international trade API: the United States, values in USD, key.
Both publish roughly two months after the month ends.
"""

from __future__ import annotations

from datetime import date
from typing import TypedDict

import httpx

# Under the web app's 30 s proxy limit, so a slow source yields a clean 503, not a cut-off.
TIMEOUT = httpx.Timeout(25.0, connect=8.0)

EUROSTAT_URL = (
    "https://ec.europa.eu/eurostat/api/comext/dissemination/statistics/1.0/data/DS-045409"
)
CENSUS_URL = "https://api.census.gov/data/timeseries/intltrade/imports/hs"

# Eurostat reporter codes (ISO alpha-2, except Greece: EL).
EU_MEMBERS: dict[str, str] = {
    "AUT": "AT", "BEL": "BE", "BGR": "BG", "HRV": "HR", "CYP": "CY", "CZE": "CZ",
    "DNK": "DK", "EST": "EE", "FIN": "FI", "FRA": "FR", "DEU": "DE", "GRC": "EL",
    "HUN": "HU", "IRL": "IE", "ITA": "IT", "LVA": "LV", "LTU": "LT", "LUX": "LU",
    "MLT": "MT", "NLD": "NL", "POL": "PL", "PRT": "PT", "ROU": "RO", "SVK": "SK",
    "SVN": "SI", "ESP": "ES", "SWE": "SE",
}  # fmt: skip

# How each covered exporter appears in each source.
EXPORTER_CODES: dict[str, dict[str, str]] = {
    "PAK": {"eurostat": "PK", "census": "5350"},
    "BGD": {"eurostat": "BD", "census": "5380"},
    "VNM": {"eurostat": "VN", "census": "5520"},
    "IND": {"eurostat": "IN", "census": "5330"},
    "TUR": {"eurostat": "TR", "census": "4890"},
    "EGY": {"eurostat": "EG", "census": "7290"},
    "MAR": {"eurostat": "MA", "census": "7140"},
    "KEN": {"eurostat": "KE", "census": "7790"},
    "LKA": {"eurostat": "LK", "census": "5420"},
    "ETH": {"eurostat": "ET", "census": "7749"},
}

COVERED_MARKETS = frozenset({*EU_MEMBERS, "USA"})


class Partner(TypedDict):
    name: str
    values: dict[str, float]  # "YYYY-MM" -> value


class MonthlyImports(TypedDict):
    source: str  # "eurostat" | "census"
    currency: str
    total: dict[str, float]  # all suppliers, per month
    partners: dict[str, Partner]  # keyed by the source's own partner code


class SourceError(RuntimeError):
    """The source didn't answer usefully. Details are for logs."""


def source_for(market: str) -> str | None:
    if market in EU_MEMBERS:
        return "eurostat"
    if market == "USA":
        return "census"
    return None


def _decode_jsonstat(data: dict) -> dict[tuple[str, str], float]:  # type: ignore[type-arg]
    """JSON-stat 2.0 -> {(partner, month): value}. Values are a flat array over all
    dimensions in `id` order; every dimension except partner and time has size 1."""
    dims: list[str] = data["id"]
    sizes: list[int] = data["size"]
    index = {d: data["dimension"][d]["category"]["index"] for d in dims}
    labels = {d: {pos: code for code, pos in index[d].items()} for d in ("partner", "time")}
    strides = [1] * len(dims)
    for i in range(len(dims) - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]
    p, t = dims.index("partner"), dims.index("time")
    out: dict[tuple[str, str], float] = {}
    for flat, value in data.get("value", {}).items():
        position = int(flat)
        partner = labels["partner"][(position // strides[p]) % sizes[p]]
        month = labels["time"][(position // strides[t]) % sizes[t]]
        out[(partner, month)] = float(value)
    return out


async def fetch_eurostat(
    client: httpx.AsyncClient, market: str, hs6: str, since: date
) -> MonthlyImports:
    params = {
        "reporter": EU_MEMBERS[market],
        "product": hs6,
        "flow": "1",  # imports
        "indicators": "VALUE_IN_EUROS",
        "freq": "M",
        "sinceTimePeriod": since.strftime("%Y-%m"),
        "format": "JSON",
    }
    try:
        response = await client.get(EUROSTAT_URL, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
        cells = _decode_jsonstat(data)
        names: dict[str, str] = data["dimension"]["partner"]["category"]["label"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise SourceError(f"Eurostat: {type(exc).__name__}: {exc}") from exc

    total: dict[str, float] = {}
    partners: dict[str, Partner] = {}
    for (code, month), value in cells.items():
        if code == "WORLD":
            total[month] = value
        elif len(code) == 2:  # ISO countries; skips EU/euro-area aggregates
            partners.setdefault(code, {"name": names.get(code, code), "values": {}})
            partners[code]["values"][month] = value
    return {"source": "eurostat", "currency": "EUR", "total": total, "partners": partners}


async def fetch_census(
    client: httpx.AsyncClient, hs6: str, since: date, api_key: str
) -> MonthlyImports:
    params = {
        "get": "CTY_CODE,CTY_NAME,GEN_VAL_MO",
        "I_COMMODITY": hs6,
        "COMM_LVL": "HS6",
        "time": f"from {since:%Y-%m}",
        "key": api_key,
    }
    try:
        response = await client.get(CENSUS_URL, params=params, timeout=TIMEOUT)
        if response.status_code == 204:  # no imports of this product at all
            rows: list[list[str]] = [[]]
        else:
            response.raise_for_status()
            rows = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        # The key is a query parameter: never include the URL in the message.
        raise SourceError(f"Census: {type(exc).__name__}") from exc

    total: dict[str, float] = {}
    partners: dict[str, Partner] = {}
    for code, name, value, *_, month in rows[1:]:
        amount = float(value or 0)
        if code == "-":  # "TOTAL FOR ALL COUNTRIES"
            total[month] = amount
        elif code.isdigit() and int(code) >= 1000:  # countries; lower codes are regions
            partners.setdefault(code, {"name": name.title(), "values": {}})
            partners[code]["values"][month] = amount
    return {"source": "census", "currency": "USD", "total": total, "partners": partners}
