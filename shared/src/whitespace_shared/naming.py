"""Readable product names from official customs descriptions."""

from __future__ import annotations

import re

from whitespace_shared.aliases import ALIASES
from whitespace_shared.niches import NICHES


def short_product(description: str) -> str:
    """Readable product name: "Bed linen: of cotton (...)" -> "Bed linen of cotton"."""
    head, _, detail = description.partition(": ")
    if not detail:
        name = head
    elif re.match(r"^(of|from|for|in|with|without|not)\b", detail) or detail.startswith("("):
        name = f"{head} {detail}"
    elif len(detail.split()) <= 2:
        name = f"{head}, {detail}"
    else:
        name = detail
    return re.sub(r"\s*\([^)]*\)", "", name).strip()


# Uncountable names that don't take a plural "s" in a search phrase.
_UNCOUNTABLE = {"rice", "salt", "tea", "coffee", "fish", "seafood", "furniture", "cement",
                "marble", "granite", "honey", "beef", "mutton", "chicken", "denim", "footwear",
                "sportswear", "workwear", "packaging", "cutlery", "medicine"}  # fmt: skip

_IRREGULAR = {"knife": "knives", "shelf": "shelves", "leaf": "leaves", "dish": "dishes",
              "brush": "brushes", "box": "boxes", "watch": "watches"}  # fmt: skip


def everyday_name(hs6: str, description: str) -> str:
    """What people call the product: 630260 -> "towels", 950662 -> "footballs".

    Uses the everyday-name dictionary (most specific code wins), then the niche name,
    then a short form of the official description.
    """
    # Preference: the most specific code, then names that point only at this product
    # ("football" over the generic "ball"), then the more common name (listed first).
    matches = [
        (len(code), -len(codes), -index, alias)
        for index, (alias, codes) in enumerate(ALIASES.items())
        for code in codes
        if hs6.startswith(code)
    ]
    if matches:
        alias = max(matches)[-1]
        last = alias.split()[-1]
        if last in _UNCOUNTABLE or last.endswith("s"):
            return alias
        if last in _IRREGULAR:
            return f"{alias[: -len(last)]}{_IRREGULAR[last]}"
        return f"{alias}s"
    niche = next((n for n in NICHES if n.matches(hs6)), None)
    if niche:
        return niche.name.lower()
    words = re.findall(r"[A-Za-z][A-Za-z-]+", short_product(description))
    return " ".join(words[:4]).lower()
