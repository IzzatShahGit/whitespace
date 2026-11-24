"""US additional duties (HTS chapter 99): the reference file and fast lookups.

`whitespace_pipeline.sources.us_hts` builds `data/us_chapter99.json` from the official
schedule (`ws-pipeline us-tariffs`). This module only reads it: no rules, no database.
The API decides how the duties combine (`whitespace_api.services.us_duties`).

Code lists name HTS lines at 8 or 10 digits, sometimes a whole 6- or 4-digit code. We
know a product only at HS6, so a lookup says how much of the HS6 a list covers: all of
it, or some of its 8-digit lines (then the caller decides how to treat the rest).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "us_chapter99.json"
EU_CODE = "EUN"  # the schedule's EU-wide row, applied to every member


@dataclass(frozen=True)
class Coverage:
    """How much of one HS6 product a code list names."""

    full: bool  # the whole HS6 (or its 4-digit heading) is listed
    lines: int  # distinct 8-digit lines listed under the HS6 (0 when `full`)


@dataclass(frozen=True)
class CodeIndex:
    """A code list, indexed by HS6."""

    whole: frozenset[str]  # 4- and 6-digit codes: everything under them is listed
    lines: dict[str, frozenset[str]]  # HS6 -> listed 8-digit lines

    @classmethod
    def of(cls, codes: Iterable[str]) -> CodeIndex:
        whole: set[str] = set()
        lines: dict[str, set[str]] = {}
        for code in codes:
            if len(code) <= 6:
                whole.add(code)
            else:
                lines.setdefault(code[:6], set()).add(code[:8])
        return cls(frozenset(whole), {k: frozenset(v) for k, v in lines.items()})

    def coverage(self, hs6: str) -> Coverage | None:
        if hs6 in self.whole or hs6[:4] in self.whole:
            return Coverage(full=True, lines=0)
        listed = self.lines.get(hs6)
        return Coverage(full=False, lines=len(listed)) if listed else None


@dataclass(frozen=True)
class CountryRate:
    heading: str  # e.g. "9903.05.62"
    rate_pct: float
    ceiling: bool  # True: tops the normal duty up to `rate_pct`; False: adds it


@dataclass(frozen=True)
class ChinaList:
    name: str  # "List 3"
    heading: str
    rate_pct: float
    codes: CodeIndex


@dataclass(frozen=True)
class Schedule:
    release: str  # "Revision 23 (2026)"
    source_url: str
    built: str  # ISO date the file was made
    country: dict[str, tuple[CountryRate, ...]]  # ISO alpha-3 or EU_CODE
    country_exempt: CodeIndex
    china: tuple[ChinaList, ...]


def parse(content: dict) -> Schedule:  # type: ignore[type-arg]
    return Schedule(
        release=content["release"],
        source_url=content["source_url"],
        built=content["built"],
        country={
            code: tuple(
                CountryRate(r["heading"], float(r["rate"]), bool(r["ceiling"])) for r in rows
            )
            for code, rows in content["country"].items()
        },
        country_exempt=CodeIndex.of(content["country_exempt"]),
        china=tuple(
            ChinaList(c["name"], c["heading"], float(c["rate"]), CodeIndex.of(c["codes"]))
            for c in content["china"]
        ),
    )


@cache
def load(path: Path = DATA_FILE) -> Schedule | None:
    """The schedule, read once per process; None if the file was never built."""
    if not path.exists():
        return None
    return parse(json.loads(path.read_text(encoding="utf-8")))
