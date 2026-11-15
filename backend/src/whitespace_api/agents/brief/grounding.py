"""The final check: every figure in the brief must come from a fact or a cited claim.

Done in code, not by a model. A point whose numbers can't be found in the facts and
claims it cites (or that cites nothing valid) is removed, and the removal is counted.
"""

from __future__ import annotations

import re

_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}\b)")


def numbers(text: str) -> set[str]:
    """Numeric tokens, normalised: "1,250.0" -> "1250", "19.5%" -> "19.5", "$164M" -> "164"."""
    clean = _THOUSANDS.sub("", text.replace("\u202f", " ").replace("\u00a0", " "))
    out = set()
    for token in _NUMBER.findall(clean):
        out.add(token.rstrip("0").rstrip(".") if "." in token else token)
    return out


def supported(text: str, evidence: list[str]) -> bool:
    """True if every number in `text` appears in the evidence texts."""
    wanted = numbers(text)
    if not wanted:
        return True
    available: set[str] = set()
    for item in evidence:
        available |= numbers(item)
    return wanted <= available
