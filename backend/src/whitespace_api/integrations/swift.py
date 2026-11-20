"""SWIFT MT700, the message banks use to issue a documentary credit, read field by field.

Most letters of credit reach exporters as an MT700 printout: tagged lines such as
":32B:USD100224,00" or ":44C:261215". Those tags are a fixed standard, so they are read
in code, exactly, with no model involved.
"""

from __future__ import annotations

import re
from datetime import date

_TAG = re.compile(r"^\s*:?(\d{2}[A-Z]?):", re.M)
_INCOTERM = re.compile(
    r"\b(EXW|FCA|FAS|FOB|CFR|CNF|C\s?&\s?F|CIF|CPT|CIP|DAP|DPU|DDP)\b"
    r"[\s,]*([A-Z][A-Za-z .'-]{2,40})?"
)
_QUANTITY = re.compile(
    r"([\d][\d,.]*)\s*(KGS?|KILOS?|KILOGRAMS?|MTS?|M/?T|METRIC\s+TONS?|TONS?|TONNES?|PCS|PIECES|"
    r"DOZENS?|SETS?|UNITS?)\b",
    re.I,
)
_ITEM = re.compile(r"(?:^|\n)\s*(?:\+|\d{1,2}[.)]|[-•])\s*")


def is_mt700(text: str) -> bool:
    tags = {m.group(1) for m in _TAG.finditer(text)}
    return "20" in tags and ("32B" in tags or "40A" in tags) and len(tags) >= 5


def fields(text: str) -> dict[str, str]:
    """{"32B": "USD100224,00", "45A": "...", ...}; a repeated tag's text is joined."""
    out: dict[str, str] = {}
    matches = list(_TAG.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end() : end].strip()
        out[m.group(1)] = f"{out[m.group(1)]}\n{body}" if m.group(1) in out else body
    return out


def swift_date(value: str | None) -> date | None:
    """ "261215" (YYMMDD) -> 2026-12-15."""
    match = re.match(r"\s*(\d{2})(\d{2})(\d{2})", value or "")
    if not match:
        return None
    yy, mm, dd = (int(g) for g in match.groups())
    try:
        return date(2000 + yy, mm, dd)
    except ValueError:
        return None


def swift_amount(value: str | None) -> tuple[str | None, float | None]:
    """ "USD100224,00" -> ("USD", 100224.0). SWIFT writes the decimal comma."""
    match = re.match(r"\s*([A-Z]{3})\s*([\d.,]+)", value or "")
    if not match:
        return None, None
    number = match.group(2).replace(".", "").replace(",", ".")
    try:
        return match.group(1), float(number)
    except ValueError:
        return match.group(1), None


def tolerance(value: str | None) -> float | None:
    """ "10/10" -> 10.0 (the smaller of plus and minus, in percent)."""
    match = re.match(r"\s*(\d{1,2})\s*/\s*(\d{1,2})", value or "")
    return float(min(int(match.group(1)), int(match.group(2)))) if match else None


def first_line(value: str | None) -> str | None:
    """The name in a party field, skipping an account line ("/12345")."""
    for line in (value or "").splitlines():
        line = line.strip()
        if line and not line.startswith("/"):
            return line
    return None


def incoterm(text: str | None) -> tuple[str | None, str | None]:
    match = _INCOTERM.search((text or "").upper())
    if not match:
        return None, None
    term = re.sub(r"\s", "", match.group(1)).replace("C&F", "CFR").replace("CNF", "CFR")
    words: list[str] = []
    for word in (match.group(2) or "").split():
        if word in ("AS", "PER", "INCOTERMS", "INCOTERM", "ACCORDING", "AND", "UNDER"):
            break
        words.append(word)
    place = " ".join(words[:3]).strip(" ,.") or None
    return term, place


def quantity(text: str | None) -> tuple[float | None, str | None]:
    match = _QUANTITY.search(text or "")
    if not match:
        return None, None
    raw = match.group(1)
    # "18.560" or "18,560" as thousands; "1.5" as a decimal.
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", raw):
        raw = re.sub(r"[.,]", "", raw)
    else:
        raw = raw.replace(",", "")
    try:
        return float(raw), match.group(2).upper()
    except ValueError:
        return None, match.group(2).upper()


def items(text: str | None) -> list[str]:
    """A "+ ..." / "1) ..." list (documents required, conditions) as separate items."""
    parts = [" ".join(p.split()) for p in _ITEM.split(text or "")]
    return [p for p in parts if len(p) > 3]


def presentation_days(value: str | None) -> int | None:
    match = re.search(r"(\d{1,3})\s*DAYS", (value or "").upper())
    return int(match.group(1)) if match else None
