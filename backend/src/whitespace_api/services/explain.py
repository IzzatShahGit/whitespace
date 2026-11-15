"""Turn a scored market into a label and plain-language reasons.

Pure functions over numbers that came from the database: nothing is invented, and
the same row always produces the same words.
"""

from __future__ import annotations

from dataclasses import dataclass

from whitespace_api.schemas.trade import Label

# Score cut-offs for the labels shown to users.
STRONG_FROM = 0.70
GOOD_FROM = 0.55
# Changes smaller than this are described as "steady".
STEADY_WITHIN = 0.005


@dataclass(frozen=True)
class Facts:
    exporter_name: str
    rival_name: str | None
    start_year: int
    end_year: int
    market_imports_usd: float
    import_growth_3y: float
    top_rival_share_change: float | None
    exporter_share: float


def label(score: float) -> Label:
    if score >= STRONG_FROM:
        return "Strong"
    if score >= GOOD_FROM:
        return "Good"
    return "Watch"


def percent(value: float) -> str:
    return f"{value * 100:.0f}%"


def money(usd: float) -> str:
    for unit, size in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if usd >= size:
            amount = usd / size
            return f"${amount:.1f}{unit}" if amount < 10 else f"${amount:.0f}{unit}"
    return f"${usd:.0f}"


def _growth(f: Facts) -> str:
    years = f"from {f.start_year} to {f.end_year}"
    if f.import_growth_3y >= STEADY_WITHIN:
        return f"Imports grew {percent(f.import_growth_3y)} a year {years}"
    if f.import_growth_3y <= -STEADY_WITHIN:
        return f"Imports fell {percent(-f.import_growth_3y)} a year {years}"
    return f"Imports held steady {years}"


def _competition(f: Facts) -> str:
    change = f.top_rival_share_change
    if f.rival_name is None or change is None:
        return f"A {money(f.market_imports_usd)} market in {f.end_year}"
    points = abs(change) * 100
    if change <= -STEADY_WITHIN:
        return f"{f.rival_name}'s share fell {points:.0f} points since {f.start_year}"
    if change >= STEADY_WITHIN:
        return f"{f.rival_name} gained {points:.0f} points of share since {f.start_year}"
    return f"{f.rival_name}'s share held steady since {f.start_year}"


def _room(f: Facts) -> str:
    if f.exporter_share < 0.01:
        return f"{f.exporter_name} holds under 1% of this market: room to grow"
    if f.exporter_share < 0.15:
        return f"{f.exporter_name} holds {percent(f.exporter_share)} of this market: room to grow"
    return f"{f.exporter_name} already holds {percent(f.exporter_share)} of this market"


def reasons(facts: Facts) -> list[str]:
    """Demand, competition, room to grow: one line each."""
    return [_growth(facts), _competition(facts), _room(facts)]
