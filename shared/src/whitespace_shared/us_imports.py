"""Monthly US imports of consumer goods: the reference file and its windows.

`whitespace_pipeline.sources.us_imports` builds `data/us_imports.json` from the US Census
Bureau (`ws-pipeline us-imports`, monthly). This module only reads it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "us_imports.json"
MONTHS = 24  # two full years: this year against last year


@dataclass(frozen=True)
class Series:
    hs6: str
    desc: str  # the Census short description, upper case
    monthly: tuple[int, ...]  # USD thousands, oldest first, MONTHS long

    @property
    def last_year(self) -> int:
        return sum(self.monthly[-12:])

    @property
    def year_before(self) -> int:
        return sum(self.monthly[:12])

    @property
    def last_quarter(self) -> int:
        return sum(self.monthly[-3:])

    @property
    def quarter_year_ago(self) -> int:
        return sum(self.monthly[-15:-12])


@dataclass(frozen=True)
class Imports:
    source: str
    source_url: str
    first_month: str  # "YYYY-MM"
    last_month: str
    built: str  # ISO date
    series: dict[str, Series]


def parse(content: dict) -> Imports:  # type: ignore[type-arg]
    series = {
        row["hs6"]: Series(row["hs6"], row["desc"], tuple(row["m"]))
        for row in content["rows"]
        if len(row["m"]) == MONTHS
    }
    return Imports(
        source=content["source"],
        source_url=content["source_url"],
        first_month=content["first_month"],
        last_month=content["last_month"],
        built=content["built"],
        series=series,
    )


@cache
def load(path: Path = DATA_FILE) -> Imports | None:
    """The shipped file, or None if it hasn't been built (the feature then hides)."""
    if not path.exists():
        return None
    return parse(json.loads(path.read_text()))
