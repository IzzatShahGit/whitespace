"""Open EU public tenders for a user's products, and company checks.

Tenders: searched on TED by the product's everyday name, then kept only if
  - the English title really contains the name (TED's search is loose), and
  - where we know the product's CPV categories, the notice uses one of them
    ("towels" then keeps terry towels and drops paper hand towels).
Results are cached per product for CACHE_HOURS and shared by every user; if TED is down
the last list is shown, marked stale.

Company checks look a name up in GLEIF (registered legal entities) and a VAT number in
VIES. They confirm a company is registered, not that it pays.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pycountry
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.core.names import core_name
from whitespace_api.core.names import norm as _norm
from whitespace_api.integrations import registers, ted
from whitespace_api.integrations.monthly_trade import EU_MEMBERS
from whitespace_api.models.profile import UserProfile
from whitespace_api.models.tenders import TenderCache
from whitespace_api.models.user import User
from whitespace_api.repositories import trade as trade_repo
from whitespace_api.schemas.tenders import (
    CompanyCheck,
    LeiMatch,
    Tender,
    TendersOut,
    VatCheck,
)
from whitespace_shared.naming import everyday_name

log = logging.getLogger(__name__)
CACHE_HOURS = 12
MAX_PER_PRODUCT = 20

# HS code prefix -> CPV prefixes for the same goods (most specific prefix wins).
# CPV: the EU's Common Procurement Vocabulary, used to classify every tender.
CPV_BY_HS: dict[str, tuple[str, ...]] = {
    "02": ("151",), "03": ("152",), "04": ("155",), "07": ("032", "153"), "08": ("032", "153"),
    "09": ("1586", "1587"), "10": ("0321", "156"), "11": ("156",), "15": ("154",),
    "16": ("151", "152"), "17": ("1583",), "18": ("1584",), "19": ("156", "158"),
    "20": ("153",), "21": ("158",), "22": ("159",), "30": ("336",), "33": ("337",),
    "34": ("3983", "3371"), "39": ("19", "4416"), "40": ("1951", "3426"), "42": ("189",),
    "44": ("441", "039"), "48": ("301", "2281", "2299", "3376"), "50": ("192",),
    "51": ("192",), "52": ("192",), "53": ("192",), "54": ("192",), "55": ("192",),
    "56": ("192", "3953"), "57": ("3953",), "58": ("192",), "59": ("192",), "60": ("192",),
    "61": ("18",), "62": ("18",), "63": ("395", "1893"), "6301": ("3951",),
    "6302": ("3951",), "6303": ("3951",), "6304": ("3951", "3952"), "6305": ("1893", "3952"),
    "6306": ("3952",), "64": ("188",), "65": ("184",), "69": ("392", "442"),
    "70": ("392", "442"), "72": ("441", "442", "443", "444"), "73": ("441", "442", "443", "444"),
    "84": ("42", "43"), "85": ("31", "32"), "87": ("34",), "90": ("38", "331"),
    "94": ("391", "3315"), "95": ("373",),
}  # fmt: skip


class NotFoundError(Exception):
    pass


class UnavailableError(Exception):
    pass


def cpv_prefixes(hs6: str) -> tuple[str, ...]:
    return CPV_BY_HS.get(hs6[:4]) or CPV_BY_HS.get(hs6[:2]) or ()


def _singular(word: str) -> str:
    return word[:-1] if len(word) > 4 and word.endswith("s") and not word.endswith("ss") else word


def title_mentions(title: str, name: str) -> bool:
    """The product name appears in the title as a phrase, plural or singular:
    "T-shirts" matches "T-shirt" but not "Shirts"; "bed linen" needs both words, in order."""
    words = [_singular(w) for w in _norm(title).split()]
    wanted = [_singular(w) for w in _norm(name).split()]
    if not wanted:
        return False
    size = len(wanted)
    return any(words[i : i + size] == wanted for i in range(len(words) - size + 1))


def select_tenders(
    notices: list[ted.Notice], *, hs6: str, name: str, today: date
) -> list[dict[str, Any]]:
    """The notices that are really about this product, soonest deadline first."""
    prefixes = cpv_prefixes(hs6)
    kept: list[dict[str, Any]] = []
    for n in notices:
        if n.deadline is not None and n.deadline < today:
            continue
        if not title_mentions(n.title, name):
            continue
        in_category = any(c.startswith(prefixes) for c in n.cpv) if prefixes else False
        if prefixes and not in_category:
            continue  # same word, different goods (paper towels vs terry towels)
        kept.append(
            {
                "number": n.number, "title": n.title, "buyer": n.buyer,
                "countries": list(n.countries),
                "published": n.published.isoformat() if n.published else None,
                "deadline": n.deadline.isoformat() if n.deadline else None,
                "value": n.value, "currency": n.currency, "url": n.url,
                "match": "category" if in_category else "keyword",
            }
        )  # fmt: skip
    kept.sort(key=lambda t: (t["deadline"] or "9999", t["number"]))
    return kept[:MAX_PER_PRODUCT]


async def _refresh(
    db: AsyncSession, http: httpx.AsyncClient, hs6: str, name: str, today: date
) -> TenderCache | None:
    try:
        notices = await ted.open_tenders(http, name, today=today)
    except ted.TedError as exc:
        log.warning("Tenders for %s unavailable: %s", hs6, exc)
        return None
    content = {"tenders": select_tenders(notices, hs6=hs6, name=name, today=today)}
    now = datetime.now(UTC)
    await db.execute(
        insert(TenderCache)
        .values(hs6=hs6, content=content, fetched_at=now)
        .on_conflict_do_update(
            index_elements=[TenderCache.hs6], set_={"content": content, "fetched_at": now}
        )
    )
    await db.commit()
    return await db.get(TenderCache, hs6, populate_existing=True)


async def for_product(
    db: AsyncSession, http: httpx.AsyncClient, hs6: str, *, force: bool = False
) -> tuple[list[Tender], datetime | None, bool, str]:
    """(tenders, fetched_at, stale, product name). Uses the cache while it's fresh."""
    product = await trade_repo.get_product(db, hs6)
    if product is None:
        raise NotFoundError(f"Unknown product {hs6}")
    name = everyday_name(hs6, product.description)
    today = datetime.now(UTC).date()
    cached = await db.get(TenderCache, hs6)
    fresh = cached is not None and cached.fetched_at > datetime.now(UTC) - timedelta(
        hours=CACHE_HOURS
    )
    stale = False
    if force or not fresh:
        refreshed = await _refresh(db, http, hs6, name, today)
        if refreshed is not None:
            cached = refreshed
        else:
            stale = cached is not None
    if cached is None:
        raise UnavailableError("EU tenders can't be reached right now. Try again later.")
    rows = cached.content.get("tenders", [])
    codes = sorted({c for r in rows for c in r["countries"]})
    names = await trade_repo.countries_by_code(db, codes)
    out = []
    for r in rows:
        deadline = date.fromisoformat(r["deadline"]) if r["deadline"] else None
        if deadline is not None and deadline < today:
            continue  # closed since it was cached
        out.append(
            Tender(
                **r,
                country_names=[names[c].name if c in names else c for c in r["countries"]],
                days_left=(deadline - today).days if deadline else None,
                hs6=hs6,
                product_name=name,
            )
        )
    return out, cached.fetched_at, stale, name


async def for_user(db: AsyncSession, http: httpx.AsyncClient, user: User) -> TendersOut:
    """Open tenders for every product in the user's profile, soonest deadline first."""
    products = await db.scalar(select(UserProfile.products).where(UserProfile.user_id == user.id))
    tenders: list[Tender] = []
    names: list[str] = []
    stale = False
    oldest: datetime | None = None
    for hs6 in list(products or [])[:5]:
        try:
            found, fetched, was_stale, name = await for_product(db, http, hs6)
        except (NotFoundError, UnavailableError):
            stale = True
            continue
        tenders.extend(found)
        names.append(name)
        stale = stale or was_stale
        if fetched and (oldest is None or fetched < oldest):
            oldest = fetched
    tenders.sort(key=lambda t: (t.deadline or date.max, t.number))
    return TendersOut(tenders=tenders, fetched_at=oldest, stale=stale, products=names)


# --- company checks ---------------------------------------------------------------


def iso2(code: str) -> str | None:
    country = pycountry.countries.get(alpha_3=code)
    return country.alpha_2 if country else None


async def check_company(
    db: AsyncSession, http: httpx.AsyncClient, name: str, country: str
) -> CompanyCheck:
    if country not in await trade_repo.countries_by_code(db, [country]):
        raise NotFoundError(f"Unknown country {country}")
    code = iso2(country)
    now = datetime.now(UTC)
    if code is None:
        return CompanyCheck(name=name, country=country, matches=[], available=False, checked_at=now)
    try:
        # Search on the identifying part: the register's full-text search misses
        # "Vossen GmbH & Co. KG" but finds "Vossen" (stored as "Vossen GmbH & Co.KG").
        records = await registers.find_lei(http, core_name(name) or name, code)
    except registers.RegisterError as exc:
        log.info("Company check unavailable: %s", exc)
        return CompanyCheck(name=name, country=country, matches=[], available=False, checked_at=now)
    wanted = core_name(name) or _norm(name)
    matches = [
        LeiMatch(
            lei=r.lei,
            name=r.name,
            city=r.city,
            active=r.entity_status == "ACTIVE",
            registration_status=r.registration_status,
            registered_as=r.registered_as,
            url=r.url,
            exact=(core_name(r.name) or _norm(r.name)) == wanted,
        )
        for r in records
    ]
    # Exact name and active first: that's the one the user means.
    matches.sort(key=lambda m: (not m.exact, not m.active))
    return CompanyCheck(
        name=name, country=country, matches=matches[:3], available=True, checked_at=now
    )


async def check_vat(http: httpx.AsyncClient, country: str, number: str) -> VatCheck:
    vies = EU_MEMBERS.get(country)
    if vies is None:
        raise NotFoundError("VAT numbers can only be checked for EU countries.")
    clean = "".join(ch for ch in number.upper() if ch.isalnum())
    if clean.startswith(vies):
        clean = clean[len(vies) :]
    try:
        result = await registers.check_vat(http, vies, clean)
    except registers.RegisterError as exc:
        raise UnavailableError(
            "The EU VAT service isn't answering for this country right now. Try again later."
        ) from exc
    return VatCheck(
        country=country, number=f"{vies}{clean}", valid=result.valid, name=result.name,
        address=result.address, checked_at=datetime.now(UTC),
    )  # fmt: skip
