"""What a shipment needs to enter a market: documents, certificates, product rules, labels.

  search   four searches: two limited to official sites (government trade guides, the
           market's customs and product-safety agencies), two open           (no tokens)
  read     the best five pages in full                                       (1 credit)
  extract  requirements, each with the exact words on its page that back it (main model)
  check    code drops any item whose quote isn't on the page it cites

No free-text summary is generated: everything shown is an item backed by a quote, so
nothing on the page is the model's own claim. ~5 Tavily credits per (product, market,
exporter), shared by every user of that lane.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

import httpx
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field

from whitespace_api.agents.brief.research import matches, rank
from whitespace_api.agents.leads import _norm, _usage
from whitespace_api.agents.llm import CallSpec
from whitespace_api.integrations import tavily
from whitespace_api.integrations.monthly_trade import EU_MEMBERS
from whitespace_api.schemas.requirements import (
    Category,
    Need,
    Requirement,
    RequirementsContent,
    RequirementSource,
)

log = logging.getLogger(__name__)

RESULTS_PER_QUERY = 6
MAX_SOURCES = 10
PAGES_TO_READ = 6  # one per topic searched; extract costs 1 credit per 5 pages
PAGE_CHARS = 16_000  # official guides are long; the product rules are often far down
MAX_ITEMS = 24
MIN_QUOTE_WORDS = 4
STOP_WORDS = frozenset({"and", "the", "for", "not", "other", "with", "similar", "products"})
QUOTE_COVERAGE = 0.9  # share of the quote's words that must appear, in order, on the page

# Government and intergovernmental sites that publish import rules.
GLOBAL_OFFICIAL = ("trade.gov", "intracen.org", "macmap.org", "wto.org", "globaltradehelpdesk.org")
MARKET_OFFICIAL: dict[str, tuple[str, ...]] = {
    "EU": ("europa.eu",),
    "USA": ("cbp.gov", "fda.gov", "cpsc.gov", "ftc.gov", "usda.gov", "epa.gov"),
    "GBR": ("gov.uk",),
    "CAN": ("canada.ca", "gc.ca"),
    "AUS": ("abf.gov.au", "agriculture.gov.au", "productsafety.gov.au", "gov.au"),
    "NZL": ("customs.govt.nz", "mpi.govt.nz", "govt.nz"),
    "JPN": ("customs.go.jp", "jetro.go.jp", "go.jp"),
    "KOR": ("customs.go.kr", "go.kr"),
    "CHN": ("customs.gov.cn", "gov.cn"),
    "IND": ("cbic.gov.in", "dgft.gov.in", "gov.in"),
    "ARE": ("moiat.gov.ae", "gov.ae"),
    "SAU": ("saber.sa", "sasoo.gov.sa", "gov.sa"),
    "CHE": ("admin.ch",),
    "NOR": ("toll.no", "regjeringen.no"),
    "TUR": ("trade.gov.tr", "gov.tr"),
    "ZAF": ("sars.gov.za", "nrcs.org.za", "gov.za"),
    "BRA": ("gov.br",),
    "MEX": ("gob.mx",),
}
# Labels that mark a government domain in most countries (gov.uk, gouv.fr, gob.mx, go.jp).
GOV_LABELS = frozenset({"gov", "gouv", "gob", "govt", "go", "gc"})


class RequirementsError(RuntimeError):
    """The requirements couldn't be researched. The message is safe to show."""


@dataclass(frozen=True)
class RequirementsDeps:
    http: httpx.AsyncClient
    search_key: str | None
    chat: Callable[[CallSpec], Runnable[Any, Any]]


@dataclass
class RequirementsRun:
    content: RequirementsContent
    searches: int = 0
    pages_read: int = 0
    calls: list[dict[str, Any]] = field(default_factory=list)


def official_domains(market: str) -> tuple[str, ...]:
    own = MARKET_OFFICIAL.get("EU" if market in EU_MEMBERS else market, ())
    return (*own, *GLOBAL_OFFICIAL)


def is_official(domain: str, market: str) -> bool:
    """A listed agency, or a government domain anywhere (cbp.gov, gov.uk, zoll.gouv.fr)."""
    if matches(domain, official_domains(market)):
        return True
    labels = domain.split(".")
    return labels[-1] == "gov" or (len(labels) >= 3 and labels[-2] in GOV_LABELS)


@dataclass(frozen=True)
class Query:
    text: str
    domains: tuple[str, ...] | None = None


def plan_queries(
    product: str,
    sector: str,
    market: str,
    exporter: str,
    market_code: str,
    scheme: str | None = None,
) -> list[Query]:
    """Templates, no tokens. The first three only search official sites. Rules are often
    written for a whole sector ("textile products"), so one search asks at that level;
    EU rules are EU-wide, so EU members are searched as "European Union"."""
    official = official_domains(market_code)
    region = "European Union" if market_code in EU_MEMBERS else market
    return [
        Query(f"{market} import requirements and documentation", ("trade.gov",)),
        Query(f"{sector} products {region} labelling requirements", official),
        Query(f"{sector} products {region} chemical restrictions safety rules", official),
        Query(
            f"{scheme} proof of origin requirements for exporters"
            if scheme
            else f"certificate of origin requirements for imports into {region}",
            official,
        ),
        Query(f"{product} import requirements {market} regulations", official),
        Query(f"import {product} into {market} certificates standards labelling"),
    ]


def _words(text: str) -> set[str]:
    return {w for w in _norm(text).split() if len(w) > 2}


def relevance(result: tavily.SearchResult, topic: set[str]) -> int:
    """How many of the product's or sector's words the page's title and address use."""
    return len(_words(f"{result.title} {result.url.replace('/', ' ').replace('-', ' ')}") & topic)


# --- extraction --------------------------------------------------------------------


class FoundItem(BaseModel):
    category: Category
    title: str = Field(description="Short name, e.g. 'Certificate of origin (REX statement)'")
    detail: str = Field(description="One or two sentences: what it is and when it applies")
    need: Need = Field(description="required | often_asked (buyers usually want it) | depends")
    issuer: str | None = Field(default=None, description="Who issues/checks it, if stated")
    quote: str = Field(description="Exact words copied from the page that support this item")
    source: str = Field(description="The page id, e.g. S2")


class Found(BaseModel):
    items: list[FoundItem]


EXTRACT_SPEC = CallSpec(tier="main", max_output_tokens=3000, schema=Found)

SYSTEM = """You list what an exporter must provide or comply with to ship {product} \
from {exporter} into {market}, using ONLY the pages given.

Include, when a page states them:
- documents for the shipment (commercial invoice, packing list, bill of lading, \
certificate of origin, import licence, ...)
- certificates and tests the goods or the exporter need
- product rules: safety, chemical limits, materials, standards the goods must meet
- labelling and marking rules (language, fibre content, origin marking, care labels, ...)
- registrations the importer or exporter must hold

Rules:
- Every item must cite one page id and copy a quote of 8 to 40 words EXACTLY as it \
appears on that page (same words, same order). The quote must itself state the rule \
(e.g. "must carry a label showing the fibre composition"), not merely name a topic or \
list headings. No such quote, no item.
- Only rules for importing into {market} (or the EU, if {market} is an EU member) that \
apply to {product} or to all goods. Skip rules for other countries or unrelated products.
- If a page limits a rule to particular goods (e.g. "wearing apparel only") and \
{product} is not among them, skip it. If it's unclear whether it covers {product}, \
use need "depends".
- A rule that only applies under one trade agreement {exporter} isn't part of (e.g. a \
regional agreement between other countries) is skipped.
- Don't merge pages, don't add knowledge of your own, don't guess fees or timelines.
- need: "required" only if the page says it is mandatory; "often_asked" if it says \
buyers or banks usually ask for it; otherwise "depends".
- At most {max_items} items, the most important first. None is a valid answer."""


def _message(sources: list[RequirementSource], texts: dict[str, str]) -> str:
    parts = [f"[{s.id}] {s.title} ({s.domain})\n{texts[s.id]}" for s in sources]
    return "Pages:\n\n" + "\n\n".join(parts)


# --- checking ------------------------------------------------------------------------


def quote_on_page(quote: str, page: str) -> bool:
    """The quote, normalised, is on the page; or nearly all of its words are, in order,
    in one place (tolerates a dropped word or different punctuation, not a paraphrase)."""
    words = _norm(quote).split()
    if len(words) < MIN_QUOTE_WORDS:
        return False
    if f" {' '.join(words)} " in f" {page} ":
        return True
    page_words = page.split()
    span = int(len(words) * 1.5) + 2
    heads = set(words[:3])
    for start, word in enumerate(page_words):
        if word not in heads:
            continue
        window = page_words[start : start + span]
        blocks = SequenceMatcher(None, words, window, autojunk=False).get_matching_blocks()
        if sum(b.size for b in blocks) >= len(words) * QUOTE_COVERAGE:
            return True
    return False


def item_key(title: str) -> str:
    return hashlib.sha256(_norm(title).encode()).hexdigest()[:16]


def _acronyms(title: str) -> set[str]:
    return set(re.findall(r"\b[A-Z]{3,}\b", title))


def _stems(text: str) -> set[str]:
    """Words cut to 5 letters: "label", "labels", "labelling" are one."""
    return {w[:5] for w in _words(text)}


def _duplicate(title: str, kept: list[Requirement]) -> bool:
    """The same requirement under another name: "EORI number registration" and
    "Economic Operator Registration and Identification (EORI) number"."""
    words, marks = _stems(title), _acronyms(title)
    for other in kept:
        theirs = _stems(other.title)
        overlap = len(words & theirs) / len(words | theirs) if words and theirs else 0.0
        # A shared acronym alone isn't enough: "GSP+ REX statement" and "GSP+ duty rates"
        # are different items.
        if overlap >= 0.6 or (overlap >= 0.3 and marks & _acronyms(other.title)):
            return True
    return False


ORDER: dict[str, int] = {"required": 0, "often_asked": 1, "depends": 2}


def check(
    found: list[FoundItem], sources: list[RequirementSource], texts: dict[str, str]
) -> RequirementsContent:
    by_id = {s.id: s for s in sources}
    pages = {sid: _norm(t) for sid, t in texts.items()}
    kept: list[Requirement] = []
    seen: set[str] = set()
    removed = 0
    for item in found:
        sid = item.source.strip()
        key = item_key(item.title)
        if sid not in by_id or not quote_on_page(item.quote, pages.get(sid, "")):
            removed += 1
            continue
        if key in seen or len(_norm(item.title)) < 3 or _duplicate(item.title, kept):
            continue
        seen.add(key)
        kept.append(
            Requirement(
                key=key,
                category=item.category,
                title=item.title.strip()[:120],
                detail=item.detail.strip()[:400],
                need=item.need,
                issuer=(item.issuer or "").strip()[:120] or None,
                quote=" ".join(item.quote.split())[:400],
                source=sid,
            )
        )
    kept.sort(key=lambda r: (ORDER[r.need], not by_id[r.source].official))
    kept = kept[:MAX_ITEMS]
    used = {r.source for r in kept}
    return RequirementsContent(
        items=kept,
        sources=[s for s in sources if s.id in used],
        research_available=True,
        removed=removed,
    )


class Duplicates(BaseModel):
    groups: list[list[int]] = Field(
        description="Groups of item numbers that describe the same requirement"
    )


DEDUPE_SPEC = CallSpec(tier="small", max_output_tokens=300, schema=Duplicates)
DEDUPE_SYSTEM = """You are given numbered import requirements. Group the numbers of \
items that describe the SAME obligation (e.g. "Fibre composition label" and "Mandatory \
fibre labelling"; "Label language" and "Translate labels into national languages"). \
Items that are related but separate obligations stay apart. Only list groups of 2 or more."""


async def merge_duplicates(
    deps: RequirementsDeps, content: RequirementsContent
) -> tuple[RequirementsContent, dict[str, Any] | None]:
    """Drop items that repeat an earlier one in other words. The model only picks
    numbers, never writes text; the first (highest-priority) item of a group is kept.
    If the call fails, the list is returned as it is."""
    items = content.items
    if len(items) < 2:
        return content, None
    listing = "\n".join(f"{i}. {r.title}: {r.detail}" for i, r in enumerate(items, 1))
    try:
        out = await deps.chat(DEDUPE_SPEC).ainvoke([("system", DEDUPE_SYSTEM), ("human", listing)])
    except Exception as exc:
        log.warning("Requirements de-duplication skipped: %s", type(exc).__name__)
        return content, None
    parsed = out.get("parsed")
    drop: set[int] = set()
    for group in parsed.groups if isinstance(parsed, Duplicates) else []:
        valid = sorted({n for n in group if 1 <= n <= len(items)})
        drop.update(valid[1:])
    kept = [r for i, r in enumerate(items, 1) if i not in drop]
    used = {r.source for r in kept}
    return (
        content.model_copy(
            update={"items": kept, "sources": [s for s in content.sources if s.id in used]}
        ),
        _usage(out.get("raw")),
    )


# --- running ------------------------------------------------------------------------


async def _search_all(
    deps: RequirementsDeps, queries: list[Query]
) -> list[list[tavily.SearchResult]]:
    """Each query's results (empty where it failed)."""
    assert deps.search_key is not None
    outcomes = await asyncio.gather(
        *(
            tavily.search(
                deps.http,
                q.text,
                deps.search_key,
                topic="general",
                max_results=RESULTS_PER_QUERY,
                time_range=None,
                include_domains=list(q.domains) if q.domains else None,
            )
            for q in queries
        ),
        return_exceptions=True,
    )
    per_query: list[list[tavily.SearchResult]] = []
    for query, outcome in zip(queries, outcomes, strict=True):
        if isinstance(outcome, BaseException):
            log.warning("Requirements search failed for %r: %s", query.text, outcome)
            per_query.append([])
        else:
            per_query.append(outcome)
    return per_query


def pages_to_read(
    per_query: list[list[tavily.SearchResult]], market: str, topic: set[str]
) -> list[str]:
    """The best page from each search in turn (official and on-topic first), so every
    topic (documents, labels, chemicals, origin) gets read, not five pages on one."""
    lists = [[r.url for r in order_sources(found, market, topic)] for found in per_query]
    chosen: list[str] = []
    for depth in range(max((len(x) for x in lists), default=0)):
        for urls in lists:
            if depth < len(urls) and urls[depth] not in chosen:
                chosen.append(urls[depth])
            if len(chosen) == PAGES_TO_READ:
                return chosen
    return chosen


def order_sources(
    found: list[tavily.SearchResult], market: str, topic: set[str]
) -> list[tavily.SearchResult]:
    """Official sites first; among them, pages about this product or sector; then the
    search's own ranking (stable sort keeps it)."""
    ranked = rank(found)
    return sorted(
        ranked,
        key=lambda r: (not is_official(r.domain, market), -min(relevance(r, topic), 2)),
    )[:MAX_SOURCES]


async def find_requirements(
    deps: RequirementsDeps,
    *,
    product: str,
    detail: str | None,
    market: str,
    market_code: str,
    exporter: str,
    sector: str | None = None,
    scheme: str | None = None,
) -> RequirementsRun:
    """`scheme` is the trade preference the lane uses (e.g. "EU GSP+"), if any: its
    proof-of-origin rules decide whether the lower duty applies."""
    empty = RequirementsContent(items=[], sources=[], research_available=False, removed=0)
    if not deps.search_key:
        return RequirementsRun(content=empty)
    sector = sector or product
    queries = plan_queries(product, sector, market, exporter, market_code, scheme)
    per_query = await _search_all(deps, queries)
    if not any(per_query):
        raise RequirementsError("The web search isn't answering right now. Please try again.")
    topic = _words(f"{product} {sector} {detail or ''}") - STOP_WORDS
    to_read = pages_to_read(per_query, market_code, topic)
    found = [r for results in per_query for r in results]
    # Pages being read come first, so they're always among the sources.
    ordered = order_sources(found, market_code, topic)
    best = [r for url in to_read for r in ordered if r.url == url]
    best += [r for r in ordered if r.url not in to_read][: max(0, MAX_SOURCES - len(best))]
    if not best:
        return RequirementsRun(content=empty, searches=len(queries))

    try:
        pages = await tavily.extract(deps.http, to_read, deps.search_key, max_chars=PAGE_CHARS)
    except tavily.SearchError as exc:
        log.warning("Reading requirement pages failed: %s", exc)
        pages = {}

    sources = [
        RequirementSource(
            id=f"S{i}",
            title=r.title,
            url=r.url,
            domain=r.domain,
            official=is_official(r.domain, market_code),
        )
        for i, r in enumerate(best, 1)
    ]
    texts = {
        s.id: f"{r.title}. {pages.get(r.url) or r.snippet}"
        for s, r in zip(sources, best, strict=True)
    }
    what = f"{product} ({detail})" if detail else product
    system = SYSTEM.format(product=what, exporter=exporter, market=market, max_items=MAX_ITEMS)
    # One call per read page (they're long), one for all the short snippets together.
    long_ids = [s for s in sources if len(texts[s.id]) > 2_000]
    short_ids = [s for s in sources if len(texts[s.id]) <= 2_000]
    groups = [[s] for s in long_ids] + ([short_ids] if short_ids else [])

    async def extract(group: list[RequirementSource]) -> Any:
        messages = [("system", system), ("human", _message(group, texts))]
        try:
            return await deps.chat(EXTRACT_SPEC).ainvoke(messages)
        except Exception as exc:  # one retry: providers fail transiently under load
            log.info("Requirements extraction retry after %s", type(exc).__name__)
            return await deps.chat(EXTRACT_SPEC).ainvoke(messages)

    outs = await asyncio.gather(*(extract(g) for g in groups), return_exceptions=True)
    merged: list[FoundItem] = []
    calls: list[dict[str, Any]] = []
    read = 0
    for out in outs:
        if isinstance(out, BaseException):
            log.warning("Requirements extraction failed: %s", type(out).__name__)
            continue
        read += 1
        calls.append(_usage(out.get("raw")))
        if (parsed := out.get("parsed")) is not None:
            merged.extend(parsed.items)
    if read == 0:
        raise RequirementsError("The requirements couldn't be read right now. Please try again.")
    content = check(merged, sources, texts)
    content, usage = await merge_duplicates(deps, content)
    if usage:
        calls.append(usage)
    return RequirementsRun(
        content=content,
        searches=len(queries),
        pages_read=len(pages),
        calls=calls,
    )
