"""Tavily web search, for the research part of market briefs.

One "basic" search costs 1 credit; the free plan has 1,000 a month. Results are short
snippets with a publication date, which is all the brief needs: pages are not fetched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import httpx

SEARCH_URL = "https://api.tavily.com/search"
TIMEOUT = httpx.Timeout(15.0, connect=5.0)
SNIPPET_CHARS = 450  # enough for a claim; keeps model input small


class SearchError(RuntimeError):
    pass


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    domain: str
    snippet: str
    published: str | None  # "YYYY-MM-DD" when the source gives one
    score: float


def _iso_date(value: str | None) -> str | None:
    """Tavily sends RFC 2822 dates ("Thu, 11 Jun 2026 08:00:00 GMT") or ISO ones."""
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError):
        return value[:10] if re.match(r"\d{4}-\d{2}-\d{2}", value) else None


def _domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host.removeprefix("www.")


async def search(
    client: httpx.AsyncClient,
    query: str,
    api_key: str,
    *,
    topic: str = "news",
    max_results: int = 5,
    time_range: str | None = "year",
    country: str | None = None,
    include_domains: list[str] | None = None,
) -> list[SearchResult]:
    """`country` (a full name, e.g. "germany") favours pages from that country;
    `include_domains` limits results to those sites (and their subdomains)."""
    payload: dict[str, object] = {
        "query": query,
        "topic": topic,
        "search_depth": "basic",
        "max_results": max_results,
        "include_answer": False,
        "include_raw_content": False,
    }
    if time_range:
        payload["time_range"] = time_range
    if country and topic == "general":
        payload["country"] = country.lower()
    if include_domains:
        payload["include_domains"] = include_domains
    try:
        response = await client.post(
            SEARCH_URL,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        results = response.json().get("results", [])
    except (httpx.HTTPError, ValueError) as exc:
        raise SearchError(f"Tavily: {type(exc).__name__}") from exc
    out = []
    for r in results:
        url = r.get("url") or ""
        if not url.startswith(("http://", "https://")):
            continue
        published = _iso_date(r.get("published_date"))
        out.append(
            SearchResult(
                title=(r.get("title") or "").strip()[:200],
                url=url,
                domain=_domain(url),
                snippet=" ".join((r.get("content") or "").split())[:SNIPPET_CHARS],
                published=published,
                score=float(r.get("score") or 0),
            )
        )
    return out


EXTRACT_URL = "https://api.tavily.com/extract"
EXTRACT_TIMEOUT = httpx.Timeout(30.0, connect=5.0)


async def extract(
    client: httpx.AsyncClient, urls: list[str], api_key: str, *, max_chars: int = 6000
) -> dict[str, str]:
    """The text of each page that could be read (url -> text), whitespace-collapsed.

    A basic extract costs 1 credit per 5 pages read. Used for directory and list pages,
    whose search snippets show only the first few company names.
    """
    if not urls:
        return {}
    try:
        response = await client.post(
            EXTRACT_URL,
            json={"urls": urls, "extract_depth": "basic"},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=EXTRACT_TIMEOUT,
        )
        response.raise_for_status()
        results = response.json().get("results", [])
    except (httpx.HTTPError, ValueError) as exc:
        raise SearchError(f"Tavily extract: {type(exc).__name__}") from exc
    pages: dict[str, str] = {}
    for r in results:
        url, text = r.get("url"), r.get("raw_content")
        if isinstance(url, str) and isinstance(text, str) and text.strip():
            pages[url] = " ".join(text.split())[:max_chars]
    return pages
