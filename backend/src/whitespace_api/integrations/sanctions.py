"""The official sanctions lists: where to get them and how to read each format.

All four are free and need no key: OFAC (US Treasury SDN list), UN Security Council
consolidated list, EU financial sanctions file, UK Sanctions List (FCDO). Files are
streamed to disk and parsed row by row, so the 50 MB UK file never sits in memory.
Each parser yields one `Listed` per name (primary name and every alias) of a person or
organisation; ships and aircraft are skipped.
"""

from __future__ import annotations

import csv
import hashlib
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx

Kind = Literal["entity", "individual"]
# Government file servers refuse or stall on library user agents.
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"
TIMEOUT = httpx.Timeout(180.0, connect=15.0)
OFAC_BASE = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports"


@dataclass(frozen=True)
class Source:
    key: str
    label: str
    files: tuple[str, ...]
    home: str  # where people can look the list up themselves


SOURCES: dict[str, Source] = {
    "ofac": Source(
        "ofac",
        "US Treasury (OFAC) SDN list",
        (f"{OFAC_BASE}/SDN.CSV", f"{OFAC_BASE}/ALT.CSV"),
        "https://sanctionssearch.ofac.treas.gov/",
    ),
    "un": Source(
        "un",
        "UN Security Council list",
        ("https://scsanctions.un.org/resources/xml/en/consolidated.xml",),
        "https://main.un.org/securitycouncil/en/content/un-sc-consolidated-list",
    ),
    "eu": Source(
        "eu",
        "EU financial sanctions list",
        (
            "https://webgate.ec.europa.eu/fsd/fsf/public/files/csvFullSanctionsList_1_1/"
            "content?token=dG9rZW4tMjAxNw",
        ),
        "https://www.sanctionsmap.eu/",
    ),
    "uk": Source(
        "uk",
        "UK Sanctions List",
        ("https://sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.csv",),
        "https://www.gov.uk/government/publications/the-uk-sanctions-list",
    ),
}


@dataclass(frozen=True)
class Listed:
    ref: str
    kind: Kind
    name: str
    program: str | None
    url: str | None


async def download(client: httpx.AsyncClient, url: str, path: Path, digest: hashlib._Hash) -> None:
    """Stream one file to disk, feeding the running checksum."""
    async with client.stream(
        "GET", url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, follow_redirects=True
    ) as response:
        response.raise_for_status()
        with path.open("wb") as out:
            async for chunk in response.aiter_bytes(1 << 16):
                out.write(chunk)
                digest.update(chunk)


def _clean(value: str | None) -> str:
    text = " ".join((value or "").split())
    return "" if text in ("-0-", "-0- ") else text


# --- OFAC: SDN.CSV (ent_num, name, type, program, ...) + ALT.CSV (ent_num, alt_num, type, name)


def parse_ofac(sdn: Path, alt: Path) -> Iterator[Listed]:
    parties: dict[str, tuple[Kind, str]] = {}
    with sdn.open(encoding="latin-1", newline="") as f:
        for row in csv.reader(f):
            if len(row) < 4 or not row[0].strip().isdigit():
                continue
            kind_text = _clean(row[2]).lower()
            if kind_text in ("vessel", "aircraft"):
                continue
            kind: Kind = "individual" if kind_text == "individual" else "entity"
            # Programs come as "SDGT] [NPWMD] [IFSR": make that "SDGT, NPWMD, IFSR".
            ref, program = row[0].strip(), _clean(row[3]).replace("] [", ", ").strip("[] ")
            parties[ref] = (kind, program)
            yield Listed(ref, kind, _clean(row[1]), program or None, _ofac_url(ref))
    with alt.open(encoding="latin-1", newline="") as f:
        for row in csv.reader(f):
            if len(row) < 4 or row[0].strip() not in parties:
                continue
            ref = row[0].strip()
            kind, program = parties[ref]
            name = _clean(row[3])
            if name:
                yield Listed(ref, kind, name, program or None, _ofac_url(ref))


def _ofac_url(ref: str) -> str:
    return f"https://sanctionssearch.ofac.treas.gov/Details.aspx?id={ref}"


# --- UN: consolidated.xml (INDIVIDUALS/INDIVIDUAL, ENTITIES/ENTITY with aliases)


def parse_un(path: Path) -> Iterator[Listed]:
    # ElementTree never fetches external entities, and Python's expat (>= 2.4.1) caps
    # entity expansion, so a hostile file can't blow up memory. The source is the UN's.
    for _, element in ET.iterparse(path, events=("end",)):  # noqa: S314
        if element.tag not in ("INDIVIDUAL", "ENTITY"):
            continue
        kind: Kind = "individual" if element.tag == "INDIVIDUAL" else "entity"
        ref = _clean(element.findtext("REFERENCE_NUMBER")) or _clean(element.findtext("DATAID"))
        program = _clean(element.findtext("UN_LIST_TYPE")) or None
        parts = ("FIRST_NAME", "SECOND_NAME", "THIRD_NAME", "FOURTH_NAME")
        primary = " ".join(p for p in (_clean(element.findtext(t)) for t in parts) if p)
        names = [primary] if primary else []
        alias_tag = "INDIVIDUAL_ALIAS" if kind == "individual" else "ENTITY_ALIAS"
        names += [_clean(a.findtext("ALIAS_NAME")) for a in element.iter(alias_tag)]
        for name in dict.fromkeys(n for n in names if n):
            yield Listed(ref, kind, name, program, SOURCES["un"].home)
        element.clear()


# --- EU: one row per (entity, name alias, ...) with ';' separators


def parse_eu(path: Path) -> Iterator[Listed]:
    seen: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            ref = _clean(row.get("Entity_LogicalId"))
            name = _clean(row.get("NameAlias_WholeName"))
            subject = _clean(row.get("Entity_SubjectType"))
            if not ref or not name or subject not in ("P", "E") or (ref, name) in seen:
                continue
            seen.add((ref, name))
            yield Listed(
                ref,
                "individual" if subject == "P" else "entity",
                name,
                _clean(row.get("Entity_Regulation_Programme")) or None,
                _clean(row.get("Entity_Regulation_PublicationUrl")) or SOURCES["eu"].home,
            )


# --- UK: a "Report Date" line, then one row per (party, name, address, ...)


def parse_uk(path: Path) -> Iterator[Listed]:
    seen: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8-sig", newline="") as f:
        first = f.readline()
        if "Unique ID" in first:  # no report-date line: that was the header
            f.seek(0)
        for row in csv.DictReader(f):
            designation = _clean(row.get("Designation Type")).lower()
            if designation not in ("entity", "individual"):
                continue
            ref = _clean(row.get("Unique ID"))
            parts = [_clean(row.get(f"Name {i}")) for i in (1, 2, 3, 4, 5, 6)]
            name = " ".join(p for p in parts if p)
            if not ref or not name or (ref, name) in seen:
                continue
            seen.add((ref, name))
            yield Listed(
                ref,
                "individual" if designation == "individual" else "entity",
                name,
                _clean(row.get("Regime Name")) or None,
                SOURCES["uk"].home,
            )


def parse(source: str, paths: list[Path]) -> Iterator[Listed]:
    if source == "ofac":
        return parse_ofac(paths[0], paths[1])
    return {"un": parse_un, "eu": parse_eu, "uk": parse_uk}[source](paths[0])
