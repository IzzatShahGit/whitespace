"""Import duty rates by partner country, for one HS6 product in one tariff area.

Two free sources, no keys, normalised to `TariffRow`s:
- WITS-TRAINS (World Bank, UNCTAD), for every market: MFN and preferential ad valorem
  rates as simple averages over the national tariff lines of the HS6 code. MFN rates
  run about three years behind; partner-specific preferences further (2021 for most
  reporters in 2026). The EU reports once, as reporter 918. XML, because the JSON
  format is about 30 times slower.
- UK Trade Tariff (HMRC), for the UK: today's duties, including every preference.

Rows carry partner "000" for the MFN rate (everyone), a country's ISO alpha-3 code, or
the source's group code for a preference given to a group (e.g. WITS "B29"). No service
says who is in a WITS group: see `whitespace_shared.tariff_schemes`.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from statistics import mean
from typing import Any, Literal, TypedDict
from xml.etree import ElementTree

import httpx

from whitespace_api.integrations.monthly_trade import EU_MEMBERS
from whitespace_shared.country_codes import COMTRADE_NUMERIC, ISO_ALPHA2, ISO_NUMERIC
from whitespace_shared.tariff_schemes import groups_for

TIMEOUT = httpx.Timeout(15.0, connect=5.0)
WITS_URL = (
    "https://wits.worldbank.org/API/V1/SDMX/V21/datasource/TRN/reporter/{reporter}"
    "/partner/{partner}/product/{hs6}/year/{year}/datatype/reported"
)
UK_URL = "https://www.trade-tariff.service.gov.uk"

MFN = "000"  # WITS partner code for "every partner": the MFN rate
EU_REPORTER = "918"  # the EU's common external tariff, reported once for all members
UK_REPORTER = "826"
# WITS serves many partners only one year at a time, so preferences are looked up in
# the latest few MFN years (one request each) and each partner's newest row is kept.
PREF_LOOKBACK_YEARS = 3

# UK Trade Tariff measure types that set the duty.
UK_STANDARD = frozenset({"103", "112"})  # third-country duty; autonomous suspension
UK_PREFERENCE = "142"  # tariff preference (quota-limited ones, 143, are left out)
UK_ALL_ORIGINS = "1011"  # "ERGA OMNES"
UK_AREA_ALIASES = {"XS": "SRB"}  # the UK tariff's own code for Serbia
UK_MAX_LINES = 12  # products split into more UK lines use WITS (one request per line)
UK_CONCURRENCY = 4
_AD_VALOREM = re.compile(r"^(\d+(?:\.\d+)?) %$")  # "12.00 %"; anything else is per unit

_FROM_NUMERIC = {code: iso3 for iso3, code in ISO_NUMERIC.items()} | {
    code: iso3 for iso3, code in COMTRADE_NUMERIC.items()
}
_FROM_ALPHA2 = {code: iso3 for iso3, code in ISO_ALPHA2.items()} | UK_AREA_ALIASES


class SourceError(RuntimeError):
    """The source didn't answer usefully. Details are for logs."""


class TariffRow(TypedDict):
    partner: str  # MFN ("000"), an ISO alpha-3 country, or a source group code
    kind: Literal["MFN", "PREF"]
    year: int
    rate: float  # percent: simple average over the ad valorem tariff lines
    min_rate: float
    max_rate: float
    lines: int  # national tariff lines under the HS6 code
    na_lines: int  # lines with per-unit duties, left out of the average
    scheme: str | None  # the preference's name, when the source gives one


class Tariffs(TypedDict):
    source: Literal["wits", "uk"]
    url: str  # where to check the figures
    rows: list[TariffRow]


def reporter_for(market: str) -> str | None:
    """The tariff area that sets `market`'s import duties (EU members share one)."""
    return EU_REPORTER if market in EU_MEMBERS else ISO_NUMERIC.get(market)


async def fetch(client: httpx.AsyncClient, reporter: str, hs6: str) -> Tariffs:
    """Duties for one product: the UK from its own tariff (WITS if it lacks the code)."""
    if reporter == UK_REPORTER and (uk := await fetch_uk(client, hs6)) is not None:
        return uk
    url = WITS_URL.format(reporter=reporter, partner=MFN, hs6=hs6, year="all")
    return {"source": "wits", "url": url, "rows": await fetch_wits(client, reporter, hs6)}


async def _all[T](calls: Sequence[Awaitable[T]]) -> list[T]:
    """Run calls together; any failure fails the lot, so partial data is never cached."""
    results = await asyncio.gather(*calls, return_exceptions=True)
    if errors := [r for r in results if isinstance(r, BaseException)]:
        raise errors[0]
    return [r for r in results if not isinstance(r, BaseException)]


# ---------- WITS-TRAINS ----------
async def fetch_wits(client: httpx.AsyncClient, reporter: str, hs6: str) -> list[TariffRow]:
    """The latest MFN rate and each partner's newest preference ([] without an MFN rate)."""
    mfn = await _wits(client, reporter, MFN, hs6, "all")
    if not mfn:
        return []
    years = sorted({r["year"] for r in mfn}, reverse=True)[:PREF_LOOKBACK_YEARS]
    batches = await _all(
        [_wits(client, reporter, "all", hs6, str(year)) for year in years]
        + [_wits(client, reporter, group, hs6, "all") for group in groups_for(reporter)]
    )
    return _newest([*mfn, *(row for batch in batches for row in batch)])


async def _wits(
    client: httpx.AsyncClient, reporter: str, partner: str, hs6: str, year: str
) -> list[TariffRow]:
    url = WITS_URL.format(reporter=reporter, partner=partner, hs6=hs6, year=year)
    try:
        response = await client.get(url, timeout=TIMEOUT)
    except httpx.HTTPError as exc:
        raise SourceError(f"WITS: {type(exc).__name__}") from exc
    if response.status_code == 404 and b"NoRecordsFound" in response.content:
        return []
    if response.status_code != 200:
        raise SourceError(f"WITS: HTTP {response.status_code} for {url}")
    return parse_wits(response.content)


def parse_wits(body: bytes) -> list[TariffRow]:
    """SDMX structure-specific data -> one row per partner and year."""
    # WITS never sends a DTD; refusing one rules out entity-expansion attacks.
    if b"<!DOCTYPE" in body or b"<!ENTITY" in body:
        raise SourceError("WITS: unexpected document type declaration")
    try:
        root = ElementTree.fromstring(body)  # noqa: S314 (no DTD, so no entities)
        return [
            _wits_row(series.get("PARTNER", ""), obs)
            for series in root.iter("Series")
            for obs in series.iter("Obs")
            if obs.get("TARIFFTYPE") in ("MFN", "PREF")
        ]
    except (ElementTree.ParseError, KeyError, ValueError) as exc:
        raise SourceError(f"WITS: {type(exc).__name__}: {exc}") from exc


def _wits_row(partner: str, obs: ElementTree.Element) -> TariffRow:
    kind: Literal["MFN", "PREF"] = "MFN" if obs.attrib["TARIFFTYPE"] == "MFN" else "PREF"
    value = obs.attrib["OBS_VALUE"]
    return {
        "partner": MFN if kind == "MFN" else _FROM_NUMERIC.get(partner, partner),
        "kind": kind,
        "year": int(obs.attrib["TIME_PERIOD"]),
        "rate": _percent(value),
        "min_rate": _percent(obs.get("MIN_RATE") or value),
        "max_rate": _percent(obs.get("MAX_RATE") or value),
        "lines": int(obs.get("TOTALNOOFLINES", "1")),
        "na_lines": int(obs.get("NBR_NA_LINES", "0")),
        "scheme": None,
    }


def _percent(value: str) -> float:
    return round(float(value), 2)  # WITS sends float noise: "9.10000038146973"


def _newest(rows: list[TariffRow]) -> list[TariffRow]:
    """Each partner's most recent row."""
    newest: dict[tuple[str, str], TariffRow] = {}
    for row in rows:
        key = (row["partner"], row["kind"])
        if key not in newest or row["year"] > newest[key]["year"]:
            newest[key] = row
    return list(newest.values())


# ---------- UK Trade Tariff ----------
@dataclass
class _LineDuties:
    """One 10-digit UK line: the duty for everyone, and lower rates by country."""

    standard: float | None  # None when the duty isn't a plain percentage
    preferences: dict[str, tuple[float, str | None]] = field(default_factory=dict)


async def fetch_uk(client: httpx.AsyncClient, hs6: str) -> Tariffs | None:
    """Today's UK duties, or None when its tariff has no plain-percentage lines for the
    code (the UK tariff follows HS 2022; a few HS 2017 codes no longer exist)."""
    heading = await _uk_get(client, f"/api/v2/headings/{hs6[:4]}")
    lines = _uk_lines(heading, hs6) if heading is not None else []
    if not lines or len(lines) > UK_MAX_LINES:
        return None
    limit = asyncio.Semaphore(UK_CONCURRENCY)

    async def line(code: str) -> dict[str, Any] | None:
        async with limit:
            return await _uk_get(client, f"/api/v2/commodities/{code}")

    documents = await _all([line(code) for code in lines])
    try:
        duties = [_uk_line_duties(doc) for doc in documents if doc is not None]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise SourceError(f"UK Trade Tariff: unexpected document: {exc!r}") from exc
    rows = _uk_rows(duties, datetime.now(UTC).year)
    if not rows:
        return None
    return {"source": "uk", "url": f"{UK_URL}/commodities/{lines[0]}", "rows": rows}


async def _uk_get(client: httpx.AsyncClient, path: str) -> dict[str, Any] | None:
    try:
        response = await client.get(UK_URL + path, timeout=TIMEOUT)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        body: dict[str, Any] = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise SourceError(f"UK Trade Tariff: {type(exc).__name__} for {path}") from exc
    return body


def _uk_lines(heading: dict[str, Any], hs6: str) -> list[str]:
    """The declarable 10-digit lines under an HS6 code, from its heading."""
    codes = set()
    for item in heading.get("included", []):
        attributes = item.get("attributes", {})
        code = str(attributes.get("goods_nomenclature_item_id", ""))
        leaf = attributes.get("leaf") and attributes.get("producline_suffix") == "80"
        if item.get("type") == "commodity" and leaf and code.startswith(hs6):
            codes.add(code)
    return sorted(codes)


def _ids(item: dict[str, Any] | None, relation: str) -> list[str]:
    data = (item or {}).get("relationships", {}).get(relation, {}).get("data") or []
    return [ref["id"] for ref in (data if isinstance(data, list) else [data])]


def _uk_rate(included: dict[tuple[str, str], Any], measure: dict[str, Any]) -> float | None:
    """The measure's duty when it's a plain percentage, else None."""
    ids = _ids(measure, "duty_expression")
    expression = included.get(("duty_expression", ids[0]), {}) if ids else {}
    match = _AD_VALOREM.match(expression.get("attributes", {}).get("base", ""))
    return float(match.group(1)) if match else None


def _uk_line_duties(document: dict[str, Any]) -> _LineDuties:
    included = {(i["type"], i["id"]): i for i in document.get("included", [])}
    standard: list[float | None] = []
    duties = _LineDuties(standard=None)
    for measure_id in _ids(document["data"], "import_measures"):
        measure = included[("measure", measure_id)]
        if _ids(measure, "additional_code"):
            continue  # applies to some goods in the line only
        kind, area = _ids(measure, "measure_type")[0], _ids(measure, "geographical_area")[0]
        rate = _uk_rate(included, measure)
        if kind in UK_STANDARD and area == UK_ALL_ORIGINS:
            standard.append(rate)
        elif kind == UK_PREFERENCE and rate is not None:
            _add_preference(duties, included, measure, area, rate)
    plain = [rate for rate in standard if rate is not None]
    duties.standard = min(plain) if plain and len(plain) == len(standard) else None
    return duties


def _add_preference(
    duties: _LineDuties,
    included: dict[tuple[str, str], Any],
    measure: dict[str, Any],
    area: str,
    rate: float,
) -> None:
    """Record `rate` for each beneficiary, keeping each country's lowest rate."""
    group = included.get(("geographical_area", area))
    members = _ids(group, "children_geographical_areas")
    scheme = group["attributes"].get("description") if group and members else None
    excluded = set(_ids(measure, "excluded_countries"))
    for code in members or [area]:
        country = _FROM_ALPHA2.get(code)
        if country is None or code in excluded:
            continue
        current = duties.preferences.get(country)
        # On a tie, keep the one with a name (a group's) for the sentence.
        if current is None or rate < current[0] or (rate == current[0] and current[1] is None):
            duties.preferences[country] = (rate, scheme)


def _uk_rows(lines: list[_LineDuties], year: int) -> list[TariffRow]:
    """Lines -> rows like WITS's: simple averages over the plain-percentage lines."""
    standard = [line.standard for line in lines if line.standard is not None]
    if not standard:
        return []
    priced = [line for line in lines if line.standard is not None]
    per_unit = len(lines) - len(priced)
    rows = [_uk_row(MFN, "MFN", year, standard, per_unit, None)]
    for country in sorted({c for line in priced for c in line.preferences}):
        offers = [line.preferences.get(country) for line in priced]
        rates = [min(s, o[0]) if o else s for s, o in zip(standard, offers, strict=True)]
        if rates != standard:  # lower on at least one line
            scheme = next(o[1] for o in offers if o is not None)
            rows.append(_uk_row(country, "PREF", year, rates, per_unit, scheme))
    return rows


def _uk_row(
    partner: str,
    kind: Literal["MFN", "PREF"],
    year: int,
    rates: list[float],
    per_unit: int,
    scheme: str | None,
) -> TariffRow:
    return {
        "partner": partner,
        "kind": kind,
        "year": year,
        "rate": round(mean(rates), 2),
        "min_rate": min(rates),
        "max_rate": max(rates),
        "lines": len(rates) + per_unit,
        "na_lines": per_unit,
        "scheme": scheme,
    }
