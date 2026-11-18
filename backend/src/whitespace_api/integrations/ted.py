"""EU public tenders from TED (Tenders Electronic Daily): free, no key.

Only open calls for competition: contract notices whose tender deadline hasn't passed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import httpx

URL = "https://api.ted.europa.eu/v3/notices/search"
TIMEOUT = httpx.Timeout(20.0, connect=5.0)
FIELDS = [
    "publication-number", "notice-title", "buyer-name", "buyer-country", "publication-date",
    "deadline-receipt-tender-date-lot", "classification-cpv", "estimated-value-lot",
    "estimated-value-cur-lot",
]  # fmt: skip
OPEN_TYPES = "(cn-standard cn-social)"


class TedError(RuntimeError):
    pass


@dataclass(frozen=True)
class Notice:
    number: str
    title: str
    buyer: str
    countries: tuple[str, ...]  # ISO alpha-3
    published: date | None
    deadline: date | None
    cpv: tuple[str, ...]
    value: float | None
    currency: str | None

    @property
    def url(self) -> str:
        return f"https://ted.europa.eu/en/notice/-/detail/{self.number}"


def _day(value: str | None) -> date | None:
    """'2026-11-23+01:00' -> date(2026, 11, 23)."""
    try:
        return date.fromisoformat(value[:10]) if value else None
    except ValueError:
        return None


def _first_text(field: object) -> str:
    """TED gives text per language ({"eng": "...", "deu": [...]}); prefer English."""
    if isinstance(field, dict):
        value = field.get("eng") or next(iter(field.values()), "")
        if isinstance(value, list):
            value = value[0] if value else ""
        return str(value).strip()
    return str(field or "").strip()


def _list(raw: dict[str, object], key: str) -> list[str]:
    value = raw.get(key)
    return [str(v) for v in value] if isinstance(value, list) else []


def parse(raw: dict[str, object]) -> Notice | None:
    number = raw.get("publication-number")
    if not isinstance(number, str):
        return None
    deadlines = sorted(
        d for d in (_day(x) for x in _list(raw, "deadline-receipt-tender-date-lot")) if d
    )
    values = []
    for v in _list(raw, "estimated-value-lot"):
        try:
            values.append(float(v))
        except ValueError:
            continue
    currencies = _list(raw, "estimated-value-cur-lot")
    published = raw.get("publication-date")
    return Notice(
        number=number,
        title=_first_text(raw.get("notice-title"))[:300],
        buyer=_first_text(raw.get("buyer-name"))[:200],
        countries=tuple(dict.fromkeys(_list(raw, "buyer-country"))),
        published=_day(published if isinstance(published, str) else None),
        deadline=deadlines[0] if deadlines else None,
        cpv=tuple(dict.fromkeys(_list(raw, "classification-cpv"))),
        value=sum(values) if values else None,
        currency=currencies[0] if currencies else None,
    )


async def open_tenders(
    client: httpx.AsyncClient, keyword: str, *, today: date, limit: int = 50
) -> list[Notice]:
    """Open contract notices whose title mentions `keyword` (any language TED indexes)."""
    phrase = keyword.replace('"', "").strip()
    query = (
        f'notice-title~"{phrase}" AND notice-type IN {OPEN_TYPES} '
        f"AND deadline-receipt-tender-date-lot>={today:%Y%m%d}"
    )
    try:
        response = await client.post(
            URL,
            json={"query": query, "fields": FIELDS, "limit": limit, "page": 1, "scope": "ACTIVE"},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        notices = response.json().get("notices", [])
    except (httpx.HTTPError, ValueError) as exc:
        raise TedError(f"TED: {type(exc).__name__}") from exc
    return [n for n in (parse(raw) for raw in notices) if n is not None]
