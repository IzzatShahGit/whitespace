"""Web research for the brief: planned by templates (no tokens), run in parallel.

Searches are built from the product, market and exporter, so they cost nothing to plan
and stay on topic. Results are de-duplicated and ranked so official and established
news sources come before unknown sites; only the best few snippets go to the model.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date

import httpx

from whitespace_api.integrations import tavily
from whitespace_api.schemas.brief import BriefSource

log = logging.getLogger(__name__)

MAX_SOURCES = 8
RESULTS_PER_QUERY = 4

# Ranked above unknown sites. Suffix match on the domain.
TRUSTED = (
    ".gov", ".gov.uk", ".gov.pk", ".gov.in", ".gov.bd", ".go.th", ".go.kr", ".go.jp",
    "europa.eu", "wto.org", "worldbank.org", "imf.org", "unctad.org", "intracen.org",
    "oecd.org", "fao.org", "reuters.com", "bloomberg.com", "ft.com", "apnews.com",
    "bbc.com", "bbc.co.uk", "economist.com", "wsj.com", "nikkei.com", "asia.nikkei.com",
    "aljazeera.com", "scmp.com", "dawn.com", "tribune.com.pk", "brecorder.com",
    "thehindu.com", "livemint.com", "economictimes.indiatimes.com", "thedailystar.net",
    "bangkokpost.com", "nationthailand.com", "koreaherald.com", "fibre2fashion.com",
    "just-style.com", "textileworld.com", "gulfnews.com", "thenationalnews.com",
)  # fmt: skip
EXCLUDED = (
    "youtube.com",
    "facebook.com",
    "instagram.com",
    "pinterest.com",
    "tiktok.com",
    "x.com",
    "twitter.com",
    "reddit.com",
    "linkedin.com",
)


@dataclass(frozen=True)
class Query:
    text: str
    topic: str  # "news" for recent developments, "general" for rules and policy pages


def plan_queries(
    product: str, sector: str, market: str, exporter: str, today: date, *, bloc: str | None = None
) -> list[Query]:
    """Four searches in everyday words: the exporter's trade, market demand, and policy.

    `bloc` is the market's trade bloc when tariffs are set there (e.g. "European Union"
    for Germany), so policy searches look where the rules are actually made.
    """
    year, rules = today.year, bloc or market
    return [
        Query(f"{exporter} {product} exports {market}", "news"),
        Query(f"{market} {product} market demand {year}", "news"),
        Query(f"{rules} import duty {sector} {exporter} {year}", "general"),
        Query(f"{exporter} {rules} trade agreement preferences", "general"),
    ]


def matches(domain: str, suffixes: tuple[str, ...]) -> bool:
    """Suffix match on whole labels: "asia.nikkei.com" matches "nikkei.com",
    "notreuters.com" does not match "reuters.com"."""
    return any(
        domain == (s := suffix.lstrip(".")) or domain.endswith(f".{s}") for suffix in suffixes
    )


def rank(results: list[tavily.SearchResult]) -> list[tavily.SearchResult]:
    unique: dict[str, tavily.SearchResult] = {}
    for r in results:
        if r.snippet and not matches(r.domain, EXCLUDED):
            unique.setdefault(r.url, r)
    return sorted(
        unique.values(), key=lambda r: (matches(r.domain, TRUSTED), r.score), reverse=True
    )


async def research(
    client: httpx.AsyncClient, api_key: str | None, queries: list[Query]
) -> tuple[list[BriefSource], dict[str, str]]:
    """Sources (S1..) and their snippets, best first. Empty if search is unavailable."""
    if not api_key:
        return [], {}
    outcomes = await asyncio.gather(
        *(
            tavily.search(client, q.text, api_key, topic=q.topic, max_results=RESULTS_PER_QUERY)
            for q in queries
        ),
        return_exceptions=True,
    )
    found: list[tavily.SearchResult] = []
    for query, outcome in zip(queries, outcomes, strict=True):
        if isinstance(outcome, BaseException):
            log.warning("Search failed for %r: %s", query, outcome)
        else:
            found.extend(outcome)
    best = rank(found)[:MAX_SOURCES]
    sources = [
        BriefSource(id=f"S{i}", title=r.title, url=r.url, domain=r.domain, published=r.published)
        for i, r in enumerate(best, 1)
    ]
    snippets = {s.id: r.snippet for s, r in zip(sources, best, strict=True)}
    return sources, snippets
