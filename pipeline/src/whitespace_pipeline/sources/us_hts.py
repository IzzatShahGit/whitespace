"""US additional import duties (HTS chapter 99), read from the official schedule.

The US charges its normal (column 1) duty plus "additional" duties listed in chapter 99
of the Harmonized Tariff Schedule. WITS-TRAINS only knows the normal duty, so landed
costs into the US were understated. This module reads the chapter 99 PDF that the US
International Trade Commission publishes (free, no key) and keeps three things:

- Country duties (U.S. note 52, headings 9903.05.01-9903.05.84): an extra percentage on
  all products of about 60 countries, either added to the normal duty ("+ 10%") or
  topping it up to a ceiling ("10%" inclusive, for the EU, Japan, South Korea,
  Switzerland and Taiwan).
- Products exempt from those country duties (note 52(b) and (e)): HTS codes.
- China's product lists (U.S. note 20, headings 9903.88.01/.02/.03/.15): HTS codes and
  each list's rate, which apply on top of the country duty.

Everything is parsed from the text, never typed in by hand, and checked for shape: a
release that parses differently fails loudly instead of writing a wrong table. The
output is a small JSON file inside `whitespace_shared` (no database rows); the API reads
it through `whitespace_shared.us_tariffs`.

Left out on purpose, and said so in the app: Section 232 product duties (steel,
aluminium, copper, vehicles, wood, semiconductors), the narrower country-specific
exemption annexes, and China's product exclusions.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import pycountry
from pypdf import PdfReader

from whitespace_pipeline.config import PipelineSettings
from whitespace_shared.us_tariffs import DATA_FILE, EU_CODE

log = logging.getLogger(__name__)

SOURCE_URL = "https://hts.usitc.gov/reststop/file?release=currentRelease&filename=Chapter%2099"
BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)"
TIMEOUT = httpx.Timeout(180.0, connect=15.0)

COUNTRY_HEADINGS = ("9903.05.01", "9903.05.84")  # note 52 and Brazil's own action
MIN_COUNTRIES = 50  # the July 2026 action names about 60; far fewer means a bad parse
MIN_CHINA_CODES = 5_000  # Lists 1-4A hold about 10,000 HTS lines

# China's lists: (name, heading, the code table's start and end, as anchored patterns).
CHINA_LISTS = (
    ("List 1", "9903.88.01", r"^\(b\) Heading 9903\.88\.01 applies", r"^\(c\) For the purposes"),
    ("List 2", "9903.88.02", r"^\(d\) Heading 9903\.88\.02 applies", r"^\(e\) For the purposes"),
    ("List 3", "9903.88.03", r"^\(f\) Heading 9903\.88\.03 applies", r"^\(g\) For the purposes"),
    ("List 4A", "9903.88.15", r"^\(s\) Heading 9903\.88\.15 applies", r"^\(t\) For the purposes"),
)
# Note 52 exemptions that are code tables: (b) the general annex, (e) pharmaceuticals.
EXEMPT_TABLES = (
    (r"^\(b\) As provided in heading 9903\.05\.86", r"^\(c\) As provided in heading"),
    (r"^\(e\) As provided in heading 9903\.05\.89", r"^\(f\) As provided in heading"),
)

# Running page furniture that pypdf returns inside the text.
_FURNITURE = re.compile(
    r"^(Harmonized Tariff Schedule of the United States.*|Annotated for Statistical Reporting"
    r" Purposes|[IVXL]+|\d+ - [IVX]+ - \d+|U\.S\. Notes \(con\.\))$",
    re.MULTILINE,
)
_RELEASE = re.compile(r"Revision (\d+) \((\d{4})\)")
_HEADING_LINE = re.compile(r"^(?:\d/)?(9903\.0[56]\.\d\d)$", re.MULTILINE)
# HTS codes as printed: 8-digit lines run together in tables ("0101.90.300101.30.00"),
# 10-digit statistical numbers in prose ("6307.90.9842", "6307.90.98.42") and whole
# 6-digit codes ("0805.90 "). Two more digits count only when a delimiter follows, so a
# run of 8-digit codes never reads as one 10-digit code.
_CODE = re.compile(r"\d{4}\.\d{2}\.\d{2}(?:\.?\d{2}(?=[^\d.]|$))?|(?<![\d.])\d{4}\.\d{2}(?![\d.])")
_PRODUCT_OF = re.compile(
    r"product of (?:a member state of )?(?:the )?(.+?)(?:,| as provided| with )"
)
_ADDED = re.compile(r"subheading ?\+ ?(\d+(?:\.\d+)?)%")
_CEILING = re.compile(r"^No change ?(\d+(?:\.\d+)?)%")
_AT_CEILING = re.compile(r"^No change ?The duty provided")
_LIST_RATE = r"additional (\d+(?:\.\d+)?) percent ad valorem rate of duty imposed by heading {}"

# Names in the schedule that pycountry doesn't resolve on its own.
NAME_FIXES = {
    "European Union": EU_CODE,
    "South Korea": "KOR",
    "Russia": "RUS",
    "Taiwan": "TWN",
    "Türkiye": "TUR",
    "Vietnam": "VNM",
    "Bahamas": "BHS",
    "Venezuela": "VEN",
}


class ParseError(RuntimeError):
    """The schedule didn't parse into the expected shape: nothing is written."""


@dataclass(frozen=True)
class CountryDuty:
    heading: str
    rate: float  # percent
    ceiling: bool  # True: tops the normal duty up to `rate`; False: adds `rate`


# ---------- download ----------
def download(settings: PipelineSettings, client: httpx.Client | None = None) -> Path:
    """Save today's chapter 99 PDF under bronze/us_hts/ (kept as published)."""
    target = settings.bronze_dir / "us_hts" / f"chapter99_{datetime.now(UTC):%Y%m%d}.pdf"
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    own = client is None
    http = client or httpx.Client(timeout=TIMEOUT, headers={"User-Agent": BROWSER_UA})
    try:
        response = http.get(SOURCE_URL, follow_redirects=True)
        response.raise_for_status()
    finally:
        if own:
            http.close()
    if not response.content.startswith(b"%PDF"):
        raise ParseError("USITC did not return a PDF")
    partial = target.with_suffix(".part")
    partial.write_bytes(response.content)
    partial.replace(target)
    log.info("chapter 99 saved: %s (%.1f MB)", target, len(response.content) / 1e6)
    return target


def pdf_text(data: bytes) -> str:
    """The PDF's text, page after page, as pypdf reads it."""
    return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(data)).pages)


# ---------- parsing (pure) ----------
def release(text: str) -> str:
    match = _RELEASE.search(text)
    if match is None:
        raise ParseError("No HTS revision found")
    return f"Revision {match.group(1)} ({match.group(2)})"


def section(text: str, start: str, end: str) -> str:
    """The text between two anchored patterns (start inclusive, end exclusive)."""
    begin = re.search(start, text, re.MULTILINE)
    if begin is None:
        raise ParseError(f"Section not found: {start}")
    stop = re.compile(end, re.MULTILINE).search(text, begin.end())
    if stop is None:
        raise ParseError(f"End of section not found: {end}")
    return text[begin.start() : stop.start()]


def codes(text: str) -> list[str]:
    """HTS codes in a table, as digits only, sorted and unique. Chapter 99 is skipped."""
    found = {c.replace(".", "") for c in _CODE.findall(text)}
    return sorted(c for c in found if not c.startswith("99"))


def iso3(name: str) -> str:
    if name in NAME_FIXES:
        return NAME_FIXES[name]
    try:
        return str(pycountry.countries.lookup(name).alpha_3)
    except LookupError as exc:
        raise ParseError(f"Unknown country in the schedule: {name!r}") from exc


def country_duties(text: str, *, minimum: int = MIN_COUNTRIES) -> dict[str, list[CountryDuty]]:
    """Each country's additional duties, keyed by ISO alpha-3 (or `EU_CODE`).

    A heading's row reads: "... articles the product of <country>, as provided ..."
    then the heading number, then the duty. Rows that say "No change" with the normal
    duty only (countries already at the ceiling) add nothing and are skipped.
    """
    heads = list(_HEADING_LINE.finditer(text))
    low, high = COUNTRY_HEADINGS
    duties: dict[str, list[CountryDuty]] = {}
    for i, head in enumerate(heads):
        heading = head.group(1)
        if not low <= heading <= high:
            continue
        before = " ".join(text[heads[i - 1].end() if i else 0 : head.start()].split())
        after_end = heads[i + 1].start() if i + 1 < len(heads) else head.end() + 600
        after = " ".join(text[head.end() : after_end].split())
        names = _PRODUCT_OF.findall(before)
        if not names:
            continue  # an exception row (e.g. donations), not a country's duty
        if _AT_CEILING.match(after):
            continue
        if ceiling := _CEILING.match(after):
            duty = CountryDuty(heading, float(ceiling.group(1)), ceiling=True)
        elif added := _ADDED.search(after[:300]):
            duty = CountryDuty(heading, float(added.group(1)), ceiling=False)
        else:
            continue  # rows that only describe exempt goods carry no rate
        duties.setdefault(iso3(names[-1].strip()), []).append(duty)
    if len(duties) < minimum:
        raise ParseError(f"Only {len(duties)} countries parsed; expected about 60")
    return duties


def list_rate(text: str, heading: str) -> float:
    match = re.search(_LIST_RATE.format(re.escape(heading)), " ".join(text.split()))
    if match is None:
        raise ParseError(f"No rate found for heading {heading}")
    return float(match.group(1))


def china_lists(text: str, *, minimum: int = MIN_CHINA_CODES) -> list[dict[str, Any]]:
    lists: list[dict[str, Any]] = []
    total = 0
    for name, heading, start, end in CHINA_LISTS:
        table = codes(section(text, start, end))
        total += len(table)
        lists.append({"name": name, "heading": heading, "rate": list_rate(text, heading),
                      "codes": table})  # fmt: skip
    if total < minimum:
        raise ParseError(f"Only {total} China codes parsed; expected about 10,000")
    return lists


def exempt_codes(text: str) -> list[str]:
    found: set[str] = set()
    for start, end in EXEMPT_TABLES:
        found.update(codes(section(text, start, end)))
    if not found:
        raise ParseError("No exempt codes parsed from note 52")
    return sorted(found)


def build(raw: str, *, built: datetime) -> dict[str, Any]:
    """The reference file's content, from the PDF's raw text. Pure."""
    edition = release(raw)  # read from the page headers, before they are stripped
    text = _FURNITURE.sub("", raw)
    duties = country_duties(text, minimum=MIN_COUNTRIES)
    return {
        "release": edition,
        "source_url": SOURCE_URL,
        "built": built.date().isoformat(),
        "country": {
            code: [{"heading": d.heading, "rate": d.rate, "ceiling": d.ceiling} for d in rows]
            for code, rows in sorted(duties.items())
        },
        "country_exempt": exempt_codes(text),
        "china": china_lists(text, minimum=MIN_CHINA_CODES),
    }


def _summary(content: dict[str, Any]) -> Iterable[str]:
    yield f"release {content['release']}: {len(content['country'])} countries"
    yield f"{len(content['country_exempt'])} exempt codes"
    for item in content["china"]:
        yield f"China {item['name']} {item['rate']}%: {len(item['codes'])} codes"


# ---------- run ----------
def run(settings: PipelineSettings, target: Path = DATA_FILE) -> Path:
    """Download (once a day), parse, and write the reference file atomically."""
    pdf = download(settings)
    content = build(pdf_text(pdf.read_bytes()), built=datetime.now(UTC))
    partial = target.with_suffix(".part")
    partial.write_text(json.dumps(content, ensure_ascii=False, separators=(",", ":")))
    partial.replace(target)
    for line in _summary(content):
        log.info(line)
    return target
