"""Sea routes between our exporters and every market, for freight estimates.

For each (exporter, country) pair: the shortest sea distance between their main container
ports, plus a road leg for landlocked countries (to their usual gateway port). Uses the
`searoute` marine network (Eurostat-derived, open data): no API, no key, runs offline.

Ports come from the curated `PORTS` list (UN/LOCODE). Countries on several coasts list
one port per coast; the shortest pair wins, so Asia -> USA lands on the west coast and
Europe -> USA on the east. Countries not listed fall back to searoute's main ports.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from whitespace_pipeline.config import PipelineSettings
from whitespace_pipeline.io import validate_against, write_parquet_atomic
from whitespace_shared.gold import SeaRoute

log = logging.getLogger(__name__)

# Main container gateways (UN/LOCODE), one per coast for multi-coast countries.
PORTS: dict[str, tuple[str, ...]] = {
    # South Asia
    "PAK": ("PKKHI", "PKBQM"), "IND": ("INNSA", "INMUN", "INMAA", "INCCU"),
    "BGD": ("BDCGP",), "LKA": ("LKCMB",), "MDV": ("MVMLE",), "MMR": ("MMRGN",),
    # East and South-East Asia
    "CHN": ("CNSHA", "CNNGB", "CNYTN", "CNXIP", "CNTAO"), "HKG": ("HKHKG",),
    "TWN": ("TWKHH",), "KOR": ("KRPUS",), "JPN": ("JPTYO", "JPUKB", "JPNGO"),
    "VNM": ("VNSGN", "VNHPH"), "THA": ("THLCH",), "MYS": ("MYPKG", "MYTPP"),
    "SGP": ("SGSIN",), "IDN": ("IDJKT", "IDSUB"), "PHL": ("PHMNL",), "KHM": ("KHKOS",),
    "BRN": ("BNMUA",),
    # Middle East
    "ARE": ("AEJEA",), "SAU": ("SAJED", "SADMN"), "QAT": ("QAHMD",), "KWT": ("KWSWK",),
    "OMN": ("OMSOH", "OMSLL"), "BHR": ("BHMSN",), "IRN": ("IRBND",), "IRQ": ("IQUQR",),
    "ISR": ("ILHFA", "ILASH"), "JOR": ("JOAQB",), "LBN": ("LBBEY",), "SYR": ("SYLTK",),
    "YEM": ("YEADE",), "TUR": ("TRAMR", "TRMER", "TRIZM"),
    # Europe
    "DEU": ("DEHAM", "DEBRV"), "NLD": ("NLRTM",), "BEL": ("BEANR",),
    "FRA": ("FRLEH", "FRFOS"), "GBR": ("GBFXT", "GBSOU"), "IRL": ("IEDUB",),
    "ITA": ("ITGOA", "ITGIT", "ITTRS"), "ESP": ("ESVLC", "ESALG", "ESBIO"),
    "PRT": ("PTSIE", "PTLEI"), "GRC": ("GRPIR",), "POL": ("PLGDN",), "SWE": ("SEGOT",),
    "DNK": ("DKAAR",), "NOR": ("NOOSL",), "FIN": ("FIHEL",), "EST": ("EETLL",),
    "LVA": ("LVRIX",), "LTU": ("LTKLJ",), "RUS": ("RULED", "RUNVS", "RUVVO"),
    "UKR": ("UAODS",), "ROU": ("ROCND",), "BGR": ("BGVAR",), "HRV": ("HRRJK",),
    "SVN": ("SIKOP",), "ALB": ("ALDRZ",), "MNE": ("MEBAR",), "MLT": ("MTMAR",),
    "CYP": ("CYLMS",), "ISL": ("ISREY",), "GEO": ("GEPTI",),
    # Africa
    "EGY": ("EGALY", "EGPSD", "EGSOK"), "MAR": ("MATNG", "MACAS"), "DZA": ("DZALG",),
    "TUN": ("TNRAD",), "LBY": ("LYTIP",), "SDN": ("SDPZU",), "DJI": ("DJJIB",),
    "KEN": ("KEMBA",), "TZA": ("TZDAR",), "MOZ": ("MZMPM", "MZBEW"), "ZAF": ("ZADUR", "ZACPT"),
    "NAM": ("NAWVB",), "AGO": ("AOLAD",), "COG": ("CGPNR",), "GAB": ("GALBV",),
    "CMR": ("CMDLA",), "NGA": ("NGAPP", "NGTIN"), "BEN": ("BJCOO",), "TGO": ("TGLFW",),
    "GHA": ("GHTEM",), "CIV": ("CIABJ",), "LBR": ("LRMLW",), "SLE": ("SLFNA",),
    "GIN": ("GNCKY",), "SEN": ("SNDKR",), "MRT": ("MRNKC",), "MDG": ("MGTOA",),
    "MUS": ("MUPLU",), "SOM": ("SOMGQ",), "ERI": ("ERMSW",), "COD": ("CDMAT",),
    # Americas
    "USA": ("USLAX", "USSEA", "USNYC", "USSAV", "USHOU"), "CAN": ("CAVAN", "CAMTR", "CAHAL"),
    "MEX": ("MXZLO", "MXVER", "MXATM"), "BRA": ("BRSSZ", "BRPNG", "BRSSA"),
    "ARG": ("ARBUE",), "CHL": ("CLSAI", "CLVAP"), "PER": ("PECLL",), "ECU": ("ECGYE",),
    "COL": ("COCTG", "COBUN"), "VEN": ("VEPBL",), "URY": ("UYMVD",), "PAN": ("PAMIT", "PABLB"),
    "CRI": ("CRMOB",), "GTM": ("GTSTC", "GTPRQ"), "HND": ("HNPCR",), "SLV": ("SVAQJ",),
    "NIC": ("NICIO",), "DOM": ("DOCAU",), "JAM": ("JMKIN",), "CUB": ("CUMAR",),
    "TTO": ("TTPOS",), "GUY": ("GYGEO",), "SUR": ("SRPBM",),
    # Oceania
    "AUS": ("AUSYD", "AUMEL", "AUBNE", "AUFRE"), "NZL": ("NZAKL", "NZTRG"),
    "PNG": ("PGPOM",), "FJI": ("FJSUV",),
}  # fmt: skip

# Landlocked countries: the usual gateway port and a rough road/rail distance to it (km).
LANDLOCKED: dict[str, tuple[str, int]] = {
    "AFG": ("PKKHI", 1600), "ARM": ("GEPTI", 350), "AUT": ("SIKOP", 450),
    "AZE": ("GEPTI", 800), "BDI": ("TZDAR", 1450), "BFA": ("CIABJ", 1150),
    "BLR": ("LTKLJ", 550), "BOL": ("CLARI", 500), "BTN": ("INCCU", 700),
    "BWA": ("ZADUR", 950), "CAF": ("CMDLA", 1450), "CHE": ("NLRTM", 800),
    "CZE": ("DEHAM", 650), "ETH": ("DJJIB", 900), "HUN": ("SIKOP", 550),
    "KAZ": ("CNLYG", 4000), "KGZ": ("CNLYG", 4500), "LAO": ("THLCH", 650),
    "LSO": ("ZADUR", 550), "LUX": ("BEANR", 300), "MDA": ("ROCND", 600),
    "MKD": ("GRSKG", 240), "MLI": ("SNDKR", 1250), "MNG": ("CNXIP", 1600),
    "MWI": ("MZBEW", 900), "NER": ("BJCOO", 1050), "NPL": ("INCCU", 1000),
    "PRY": ("ARBUE", 1300), "RWA": ("TZDAR", 1500), "SRB": ("GRSKG", 600),
    "SSD": ("KEMBA", 1600), "SVK": ("SIKOP", 600), "SWZ": ("MZMPM", 220),
    "TCD": ("CMDLA", 1800), "TJK": ("IRBND", 2700), "TKM": ("IRBND", 1600),
    "UGA": ("KEMBA", 1150), "UZB": ("IRBND", 2600), "ZMB": ("TZDAR", 2000),
    "ZWE": ("MZBEW", 560), "BIH": ("HRPLE", 200),
}  # fmt: skip

MAX_FALLBACK_PORTS = 3


@dataclass(frozen=True)
class Port:
    code: str
    name: str
    lon: float
    lat: float


@dataclass(frozen=True)
class Gateway:
    ports: tuple[Port, ...]
    inland_km: int  # 0 unless landlocked


def _searoute() -> Any:
    import searoute  # type: ignore[import-untyped]  # heavy; only needed for this stage

    return searoute


def load_ports() -> dict[str, Port]:
    """Every port searoute knows, by UN/LOCODE."""
    sr = _searoute()
    path = Path(os.path.dirname(sr.__file__)) / "data" / "ports.geojson"
    out: dict[str, Port] = {}
    for f in json.loads(path.read_text())["features"]:
        p = f["properties"]
        lon, lat = f["geometry"]["coordinates"]
        out[p["port"]] = Port(code=p["port"], name=p["name"], lon=lon, lat=lat)
    return out


def main_ports() -> dict[str, list[str]]:
    """searoute's own "main" ports (t == 1) by ISO2 prefix, for countries we don't list."""
    sr = _searoute()
    path = Path(os.path.dirname(sr.__file__)) / "data" / "ports.geojson"
    by_country: dict[str, list[str]] = {}
    for f in json.loads(path.read_text())["features"]:
        p = f["properties"]
        if p.get("t") == 1:
            by_country.setdefault(p["port"][:2], []).append(p["port"])
    return by_country


def iso2(iso3: str) -> str | None:
    import pycountry

    found = pycountry.countries.get(alpha_3=iso3)
    return found.alpha_2 if found else None


def gateway(country: str, ports: dict[str, Port], mains: dict[str, list[str]]) -> Gateway | None:
    if country in LANDLOCKED:
        code, km = LANDLOCKED[country]
        return Gateway((ports[code],), km) if code in ports else None
    codes = [c for c in PORTS.get(country, ()) if c in ports]
    if not codes and (two := iso2(country)):
        codes = mains.get(two, [])[:MAX_FALLBACK_PORTS]
    if not codes:
        return None
    return Gateway(tuple(ports[c] for c in codes), 0)


def shortest(a: Gateway, b: Gateway) -> tuple[float, Port, Port]:
    """The port pair with the shortest sea distance (nautical miles)."""
    sr = _searoute()
    best: tuple[float, Port, Port] | None = None
    for pa in a.ports:
        for pb in b.ports:
            if pa.code == pb.code:
                nm = 0.0
            else:
                route = sr.searoute([pa.lon, pa.lat], [pb.lon, pb.lat], units="naut")
                nm = float(route["properties"]["length"])
            if best is None or nm < best[0]:
                best = (nm, pa, pb)
    assert best is not None
    return best


def _origin_rows(origin: str, countries: list[str]) -> list[dict[str, object]]:
    """Every route from one exporter (runs in a worker process)."""
    ports = load_ports()
    mains = main_ports()
    a = gateway(origin, ports, mains)
    if a is None:
        log.warning("No port for exporter %s", origin)
        return []
    rows: list[dict[str, object]] = []
    for dest in countries:
        b = gateway(dest, ports, mains)
        if dest == origin or b is None:
            continue
        nm, pa, pb = shortest(a, b)
        rows.append(
            {
                "origin": origin,
                "dest": dest,
                "sea_nm": round(nm, 1),
                "origin_port": pa.name,
                "origin_port_code": pa.code,
                "dest_port": pb.name,
                "dest_port_code": pb.code,
                "origin_inland_km": a.inland_km,
                "dest_inland_km": b.inland_km,
            }
        )
    return rows


def compute(exporters: Iterable[str], countries: Iterable[str]) -> pl.DataFrame:
    """All routes, one worker process per exporter (each builds its own marine graph)."""
    from concurrent.futures import ProcessPoolExecutor

    targets = sorted(set(countries))
    origins = list(dict.fromkeys(exporters))
    workers = max(1, min(len(origins), (os.cpu_count() or 2) - 1))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        chunks = list(pool.map(_origin_rows, origins, [targets] * len(origins)))
    rows = [row for chunk in chunks for row in chunk]
    ports, mains = load_ports(), main_ports()
    no_port = sorted(c for c in targets if gateway(c, ports, mains) is None)
    log.info("routes: %s pairs; no port for %s countries: %s", len(rows), len(no_port), no_port)
    return pl.DataFrame(rows)


def run(settings: PipelineSettings) -> Path:
    gold = settings.gold_dir / f"V{settings.baci_version}"
    countries = pl.read_parquet(gold / "countries.parquet")["iso3"].unique().to_list()
    frame = compute(settings.exporters, countries)
    validate_against(frame, SeaRoute)
    out = settings.gold_dir / "sea_routes.parquet"  # independent of the BACI release
    write_parquet_atomic(frame, out)
    return out
