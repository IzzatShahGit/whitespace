"""Find companies to contact: importers in a market, or manufacturers in a source country.

  search    three web searches + one trade-fair search, planned by templates (no tokens)
  read      the best few directory/list pages, whose snippets cut off      (1 credit)
  extract   companies and events from the text, each citing its page   (small model)
  check     every name must appear on the page it cites; websites too      (code)

About 5 Tavily credits per (product, country, side), shared by every user. Only
company-level details are kept, never people's names or personal contact details.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field

from whitespace_api.agents.brief.research import matches, rank
from whitespace_api.agents.llm import CallSpec
from whitespace_api.core.names import core_name
from whitespace_api.core.names import norm as _norm
from whitespace_api.integrations import tavily
from whitespace_api.schemas.lead import (
    CompanyKind,
    Lead,
    LeadEvent,
    LeadsContent,
    LeadSide,
    LeadSource,
)

log = logging.getLogger(__name__)

RESULTS_PER_QUERY = 6
MAX_SOURCES = 12
PAGES_TO_READ = 5  # one extract credit covers five pages
PAGE_CHARS = 10_000  # directory pages carry a lot of navigation before the listings
BATCH_CHARS = 8_000  # text per extraction call
MAX_COMPANIES = 24
MAX_EVENTS = 6

# Directories, marketplaces and data vendors: good places to look, never a lead themselves.
NOT_A_COMPANY = {
    "europages", "kompass", "alibaba", "indiamart", "tradeindia", "go4worldbusiness",
    "made in china", "global sources", "globalsources", "exporthub", "tradekey", "volza",
    "panjiva", "importgenius", "import genius", "zauba", "yellow pages", "yellowpages",
    "dnb", "dun bradstreet", "zoominfo", "amazon", "ebay", "tridge", "seair", "eximpedia",
    "tradewheel", "ec21", "ecplaza", "thomasnet", "wikipedia",
}  # fmt: skip
# B2B marketplaces hold anonymous buy requests, not company names: ranked last, never read.
MARKETPLACES = (
    "go4worldbusiness.com", "tradewheel.com", "alibaba.com", "indiamart.com",
    "tradeindia.com", "made-in-china.com", "globalsources.com", "exporthub.com",
    "tradekey.com", "ec21.com", "ecplaza.net", "tridge.com", "volza.com", "panjiva.com",
    "importgenius.com", "seair.co.in", "eximpedia.app", "amazon.com", "ebay.com",
)  # fmt: skip
# People-data sites: never used at all.
PEOPLE_DATA = ("rocketreach.co", "zoominfo.com", "apollo.io", "signalhire.com", "lusha.com")
# Pages that list many companies of the kind we want; read in full when found.
LISTY = {
    "buyers": re.compile(
        r"importer|distribut|wholesal|retailer|brands|buyers|stockist|chains|"
        r"gro(ss|ß)h[äa]nd|importeur|mayorista|grossiste|groothandel|list|directory|"
        r"top \d+|leading|largest",
        re.I,
    ),
    "suppliers": re.compile(
        r"manufactur|exporter|factor(y|ies)|producer|maker|supplier|mills|companies|list|"
        r"directory|top \d+|leading|largest",
        re.I,
    ),
}


class LeadsError(RuntimeError):
    """The list couldn't be made. The message is safe to show."""


@dataclass(frozen=True)
class LeadsDeps:
    http: httpx.AsyncClient
    search_key: str | None
    chat: Callable[[CallSpec], Runnable[Any, Any]]  # llm.get_chat_model, or a fake in tests


@dataclass
class LeadsRun:
    content: LeadsContent
    searches: int = 0
    pages_read: int = 0
    calls: list[dict[str, Any]] = field(default_factory=list)


# --- planning ---------------------------------------------------------------------


def plan_queries(
    product: str,
    country: str,
    side: LeadSide,
    year: int,
    local: str | None = None,
    sector: str | None = None,
) -> list[str]:
    """Searches aimed at pages that name companies; `local` is one in the market's own
    business language. The last search looks for trade fairs."""
    if side == "buyers":
        queries = [
            f"{product} importers and distributors in {country}",
            f"{product} wholesalers {country}",
            f"leading {product} brands and retailers in {country}",
        ]
    else:
        queries = [
            f"{product} manufacturers in {country}",
            f"{product} exporters {country}",
            f"top {product} factories in {country} list",
        ]
    if local:
        queries.append(local)
    industry = f"{product} {sector}" if sector and sector not in product else product
    return [*queries, f"{industry} trade fair {country} {year} exhibitors"]


class LocalQuery(BaseModel):
    query: str | None = Field(
        description="One search query in the country's main business language, or null "
        "if that language is English"
    )


LOCAL_SPEC = CallSpec(tier="small", max_output_tokens=80, schema=LocalQuery)
LOCAL_ASK = {
    "buyers": "Write one web search query, in the main business language of {country}, "
    "that finds companies in {country} which import or wholesale {product}. Use the words "
    "local businesses would use (e.g. German: Großhandel, Importeur). Max 8 words.",
    "suppliers": "Write one web search query, in the main business language of {country}, "
    "that finds manufacturers of {product} in {country}. Max 8 words.",
}


async def local_query(
    deps: LeadsDeps, product: str, country: str, side: LeadSide
) -> tuple[str | None, dict[str, Any] | None]:
    """(query, usage): None when the market's business language is English or on error."""
    try:
        out = await deps.chat(LOCAL_SPEC).ainvoke(
            [("human", LOCAL_ASK[side].format(country=country, product=product))]
        )
    except Exception as exc:
        log.warning("Local-language query skipped: %s", type(exc).__name__)
        return None, None
    parsed: LocalQuery | None = out.get("parsed")
    query = " ".join((parsed.query or "").split())[:120] if parsed else ""
    return query or None, _usage(out.get("raw"))


# --- the model's part ---------------------------------------------------------------


class FoundCompany(BaseModel):
    name: str = Field(description="The company's name exactly as written on the page")
    city: str | None = Field(default=None, description="City, if the page says")
    kind: CompanyKind
    handles: str = Field(description="What they deal in, at most 10 words")
    website: str | None = Field(default=None, description="Only if written on the page")
    source: str = Field(description="Id of the page it appears on, e.g. S3")


class FoundEvent(BaseModel):
    name: str = Field(description="Trade fair name exactly as written on the page")
    city: str | None = None
    when: str | None = Field(default=None, description="Dates as written, if given")
    source: str


class Found(BaseModel):
    companies: list[FoundCompany]
    events: list[FoundEvent]


# The main model: the small one misses most names in long directory pages. Affordable
# because each list is cached and shared by every user.
EXTRACT_SPEC = CallSpec(tier="main", max_output_tokens=3000, schema=Found)

SYSTEM = """You extract real companies from web pages for a trade lead list.
Rules:
- Be thorough: list every qualifying company named anywhere in the pages, including \
brands and shops whose own website is one of the pages. Most relevant first, at most \
{max_companies}.
- Only companies whose name is written in the page text. Copy the name exactly. Never \
add companies from memory.
- name is always a company or brand name, never a person's name (if a page shows an \
owner's name, use the business name instead).
- Leave out companies dealing in a different product with a similar name (e.g. paper \
towels when the product is cotton terry towels).
- {who}
- Skip directories, marketplaces, data vendors, news sites, government bodies and trade \
associations: they are not companies to contact.
- website: only a web address written in that page's text (or the page's own site if \
it is the company's), else null. city: only if written, else null.
- No people's names, phone numbers or personal email addresses.
- events: only trade fairs in {country} whose focus includes {product} or its industry \
(e.g. home textiles for towels). Leave out unrelated fairs. Empty if none."""

WHO = {
    "buyers": "Keep only companies based in {country} that import, distribute, wholesale "
    "or retail {product} (or that sell it under their brand).",
    "suppliers": "Keep only companies based in {country} that make or export {product}.",
}


def _message(sources: list[LeadSource], texts: dict[str, str]) -> str:
    parts = [f"[{s.id}] {s.title} ({s.domain})\n{texts[s.id]}" for s in sources]
    return "Pages:\n\n" + "\n\n".join(parts)


# --- checking ---------------------------------------------------------------------


def on_page(name: str, page: str) -> bool:
    core = core_name(name)
    return len(core) >= 4 and f" {core} " in f" {page} "


def _domain(url: str) -> str | None:
    text = url.strip()
    if not text:
        return None
    host = urlparse(text if "://" in text else f"https://{text}").netloc.lower()
    host = host.split("@")[-1].split(":")[0].removeprefix("www.")
    return host if "." in host and " " not in host else None


def checked_website(website: str | None, raw_page: str, source_domain: str) -> str | None:
    """The company's site, only if that address is on the cited page (or is the page)."""
    host = _domain(website or "")
    if host is None:
        return None
    if host == source_domain or host in raw_page.lower():
        return f"https://{host}"
    return None


def event_key(name: str) -> str:
    """ "Heimtextil 2026" and "Heimtextil Frankfurt" are one fair: its first word."""
    words = [w for w in _norm(name).split() if not w.isdigit()]
    return words[0] if words else ""


def is_directory(name: str) -> bool:
    core = core_name(name)
    return any(core == d or core.startswith(f"{d} ") for d in NOT_A_COMPANY)


MONTHS: dict[str, int] = {
    word: number
    for number, words in enumerate(
        (
            "january jan januar janvier enero",
            "february feb februar fevrier février febrero",
            "march mar märz maerz mars marzo",
            "april apr avril abril",
            "may mai mayo",
            "june jun juni juin junio",
            "july jul juli juillet julio",
            "august aug août aout agosto",
            "september sep sept septembre septiembre",
            "october oct oktober octobre octubre",
            "november nov novembre noviembre",
            "december dec dezember décembre decembre diciembre",
        ),
        start=1,
    )
    for word in words.split()
}


def is_past(name: str, when: str | None, year: int | None, month: int | None = None) -> bool:
    """A fair that has already happened: its name and dates mention only years before
    `year` ("TEXPO 2024"), or only months before `month` of this year ("21-24 April 2026"
    in November). Ranges that reach a later year or month are kept."""
    text = f"{name} {when or ''}"
    years = [int(y) for y in re.findall(r"\b(20\d\d)\b", text)]
    if year is None or not years:
        return False
    if max(years) != year:
        return max(years) < year
    words = re.findall(r"[^\W\d_]+", (when or "").lower())
    months = [MONTHS[w] for w in words if w in MONTHS]
    return month is not None and bool(months) and max(months) < month


def check(
    found: Found | None,
    sources: list[LeadSource],
    texts: dict[str, str],
    year: int | None = None,
    month: int | None = None,
) -> LeadsContent:
    """Keep only companies and events that their cited page really names (and fairs
    that haven't already happened)."""
    by_id = {s.id: s for s in sources}
    pages = {sid: _norm(t) for sid, t in texts.items()}
    removed = 0
    companies: list[Lead] = []
    seen: set[str] = set()
    for c in found.companies if found else []:
        sid = c.source.strip()
        source = by_id.get(sid)
        key = core_name(c.name)
        if key in seen:
            continue
        if source is None or is_directory(c.name) or not on_page(c.name, pages[sid]):
            removed += 1
            continue
        seen.add(key)
        companies.append(
            Lead(
                name=c.name.strip()[:120],
                city=(c.city or "").strip()[:60] or None,
                kind=c.kind,
                handles=" ".join(c.handles.split()[:12]),
                website=checked_website(c.website, texts[sid], source.domain),
                source=sid,
            )
        )
        if len(companies) == MAX_COMPANIES:
            break
    events: list[LeadEvent] = []
    fairs: set[str] = set()
    for e in found.events if found else []:
        sid = e.source.strip()
        fair = event_key(e.name)
        if fair in fairs or is_past(e.name, e.when, year, month):
            continue
        if sid in by_id and on_page(e.name, pages[sid]):
            fairs.add(fair)
            events.append(
                LeadEvent(
                    name=e.name.strip()[:120],
                    city=(e.city or "").strip()[:60] or None,
                    when=(e.when or "").strip()[:60] or None,
                    source=sid,
                )
            )
        else:
            removed += 1
    return LeadsContent(
        companies=companies,
        events=events[:MAX_EVENTS],
        sources=sources,
        research_available=True,
        removed=removed,
    )


# --- running ----------------------------------------------------------------------


def _usage(raw: Any) -> dict[str, Any]:
    meta = getattr(raw, "usage_metadata", None) or {}
    model = (getattr(raw, "response_metadata", None) or {}).get("model_name", "unknown")
    return {
        "model": str(model),
        "input_tokens": int(meta.get("input_tokens", 0)),
        "output_tokens": int(meta.get("output_tokens", 0)),
    }


def batches(sources: list[LeadSource], texts: dict[str, str]) -> list[list[LeadSource]]:
    """Groups of pages of about BATCH_CHARS each: small models list far more of the
    names in a short text than in a long one. Runs in parallel."""
    groups: list[list[LeadSource]] = []
    size = BATCH_CHARS
    for source in sources:
        if size + len(texts[source.id]) > BATCH_CHARS and (not groups or groups[-1]):
            groups.append([])
            size = 0
        groups[-1].append(source)
        size += len(texts[source.id])
    return groups


def pages_worth_reading(results: list[tavily.SearchResult], side: LeadSide) -> list[str]:
    """List and directory pages of the right kind: their snippets show only a few names."""
    pattern = LISTY[side]
    return [
        r.url
        for r in results
        if not matches(r.domain, MARKETPLACES) and pattern.search(f"{r.title} {r.url}")
    ][:PAGES_TO_READ]


def order_sources(found: list[tavily.SearchResult]) -> list[tavily.SearchResult]:
    """Best first, marketplaces last; people-data sites and encyclopaedias dropped."""
    usable = [r for r in rank(found) if not matches(r.domain, (*PEOPLE_DATA, "wikipedia.org"))]
    return sorted(usable, key=lambda r: matches(r.domain, MARKETPLACES))[:MAX_SOURCES]


async def _search_all(
    deps: LeadsDeps, queries: list[str], country: str | None
) -> tuple[list[tavily.SearchResult], int]:
    """Run every search at once; (results, searches that succeeded)."""
    assert deps.search_key is not None
    outcomes = await asyncio.gather(
        *(
            tavily.search(
                deps.http,
                q,
                deps.search_key,
                topic="general",
                max_results=RESULTS_PER_QUERY,
                time_range=None,
                country=country,
            )
            for q in queries
        ),
        return_exceptions=True,
    )
    found: list[tavily.SearchResult] = []
    ok = 0
    for query, outcome in zip(queries, outcomes, strict=True):
        if isinstance(outcome, BaseException):
            log.warning("Lead search failed for %r: %s", query, outcome)
        else:
            ok += 1
            found.extend(outcome)
    return found, ok


async def find_leads(
    deps: LeadsDeps,
    *,
    product: str,
    country: str,
    side: LeadSide,
    year: int,
    month: int | None = None,
    sector: str | None = None,
    detail: str | None = None,
) -> LeadsRun:
    """`detail` is the official product description, to tell e.g. terry towels from
    paper towels."""
    empty = LeadsContent(companies=[], events=[], sources=[], research_available=False, removed=0)
    if not deps.search_key:
        return LeadsRun(content=empty)
    calls: list[dict[str, Any]] = []
    local, usage = await local_query(deps, product, country, side)
    if usage:
        calls.append(usage)
    queries = plan_queries(product, country, side, year, local, sector)
    found, ok = await _search_all(deps, queries, country)
    searches = len(queries)
    if ok == 0:  # e.g. a country name the search's boost doesn't know: try without it
        found, _ = await _search_all(deps, queries, None)
        searches += len(queries)
    best = order_sources(found)
    if not best:
        return LeadsRun(content=empty, searches=searches, calls=calls)

    try:
        pages = await tavily.extract(
            deps.http, pages_worth_reading(best, side), deps.search_key, max_chars=PAGE_CHARS
        )
    except tavily.SearchError as exc:
        log.warning("Reading lead pages failed: %s", exc)
        pages = {}

    sources = [
        LeadSource(id=f"S{i}", title=r.title, url=r.url, domain=r.domain)
        for i, r in enumerate(best, 1)
    ]
    texts = {
        s.id: f"{r.title}. {pages.get(r.url) or r.snippet}"
        for s, r in zip(sources, best, strict=True)
    }
    what = f"{product} ({detail})" if detail else product
    system = SYSTEM.format(
        who=WHO[side].format(country=country, product=what),
        country=country,
        product=product,
        max_companies=MAX_COMPANIES,
    )
    outs = await asyncio.gather(
        *(
            deps.chat(EXTRACT_SPEC).ainvoke([("system", system), ("human", _message(group, texts))])
            for group in batches(sources, texts)
        ),
        return_exceptions=True,
    )
    merged = Found(companies=[], events=[])
    read = 0
    for out in outs:
        if isinstance(out, BaseException):
            log.warning("Lead extraction batch failed: %s", type(out).__name__)
            continue
        read += 1
        calls.append(_usage(out.get("raw")))
        if (parsed := out.get("parsed")) is not None:
            merged.companies.extend(parsed.companies)
            merged.events.extend(parsed.events)
    if read == 0:
        raise LeadsError("The company list couldn't be read right now. Please try again.")
    content = check(merged, sources, texts, year, month)
    return LeadsRun(
        content=content,
        searches=searches,
        pages_read=len(pages),
        calls=calls,
    )
