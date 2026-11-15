"""Amounts the way people write them: "18 lakh", "2.5 crore", "500k", "5 tons".

Parsed in code so a model never has to do the arithmetic (mirrors frontend/src/lib/money.ts).
"""

from __future__ import annotations

import re

_NUMBER = re.compile(r"^(\d+(?:\.\d+)?)([a-z]*)$")
_SCALES = {
    **dict.fromkeys(("", "usd", "dollars"), 1.0),
    **dict.fromkeys(("k", "thousand", "hazar", "hazaar"), 1e3),
    **dict.fromkeys(("l", "lac", "lacs", "lakh", "lakhs"), 1e5),
    **dict.fromkeys(("m", "mn", "million", "millions"), 1e6),
    **dict.fromkeys(("cr", "crore", "crores"), 1e7),
    **dict.fromkeys(("b", "bn", "billion", "billions", "arab"), 1e9),
}
_KG = {
    **dict.fromkeys(("", "kg", "kgs", "kilo", "kilos", "kilogram", "kilograms"), 1.0),
    **dict.fromkeys(("t", "mt", "ton", "tons", "tonne", "tonnes"), 1000.0),
}


def _parse(text: str, scales: dict[str, float]) -> float | None:
    match = _NUMBER.match(re.sub(r"[,\s_]", "", text.strip().lower()))
    if not match or match.group(2) not in scales:
        return None
    value = float(match.group(1)) * scales[match.group(2)]
    return value if value > 0 else None


def parse_amount(text: str) -> float | None:
    """ "18 lakh" -> 1_800_000.0; None if unreadable or not positive."""
    return _parse(text, _SCALES)


def parse_kg(text: str) -> float | None:
    """ "5 tons" -> 5000.0, "800 kg" -> 800.0, "1200" -> 1200.0 (kg)."""
    return _parse(text, _KG)
