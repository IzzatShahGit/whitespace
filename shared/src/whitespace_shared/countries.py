"""Country display names.

BACI's names are written for statisticians: abbreviations ("Rep.", "Isds"), historic
labels ("Fed. Rep. of Germany (...1990)" is used for today's Germany) and a few
mis-encoded characters. `display_name` turns them into names people recognise.
"""

from __future__ import annotations

import re

# Names people actually use, where the official one differs.
OVERRIDES: dict[str, str] = {
    "USA": "United States",
    "GBR": "United Kingdom",
    "DEU": "Germany",
    "BEL": "Belgium",
    "KOR": "South Korea",
    "PRK": "North Korea",
    "RUS": "Russia",
    "VNM": "Vietnam",
    "LAO": "Laos",
    "MDA": "Moldova",
    "TZA": "Tanzania",
    "BOL": "Bolivia",
    "VEN": "Venezuela",
    "IRN": "Iran",
    "SYR": "Syria",
    "HKG": "Hong Kong",
    "MAC": "Macao",
    "COD": "DR Congo",
    "COG": "Republic of the Congo",
    "CZE": "Czechia",
    "TUR": "Türkiye",
    "CIV": "Côte d'Ivoire",
    "S19": "Other Asia (n.e.s.)",
    "R20": "Other EFTA (n.e.s.)",
    "ZA1": "Southern African Customs Union",
}

_ABBREVIATIONS = [
    (r"\bDem\. People's Rep\.", "Democratic People's Republic"),
    (r"\bRep\.", "Republic"),
    (r"\bDem\.", "Democratic"),
    (r"\bFed\.", "Federal"),
    (r"\bIsds\b", "Islands"),
    (r"\bTerr\.", "Territory"),
    (r"\bBr\.", "British"),
    (r"\bFr\.", "French"),
    (r"\bN\.", "Northern"),
    (r"\bMisc\.", "Minor"),
]
_HISTORIC_SUFFIX = re.compile(r"\s*\(\.\.\.\d{4}\)$")


def _fix_encoding(name: str) -> str:
    """Undo UTF-8 text that was decoded as Latin-1 ("BarthÃ©lemy" -> "Barthélemy")."""
    if "Ã" not in name:
        return name
    try:
        return name.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return name


def display_name(code: str, raw: str) -> str:
    if code in OVERRIDES:
        return OVERRIDES[code]
    name = _HISTORIC_SUFFIX.sub("", _fix_encoding(raw.strip()))
    for pattern, replacement in _ABBREVIATIONS:
        name = re.sub(pattern, replacement, name)
    return name
