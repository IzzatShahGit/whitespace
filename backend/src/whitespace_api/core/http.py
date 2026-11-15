"""One pooled HTTP client per process for outbound calls (closed on shutdown in main.py).

Routes get it through the `HttpClient` dependency so tests can swap in a mock transport.
"""

from __future__ import annotations

from functools import lru_cache

import httpx


@lru_cache
def http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(headers={"User-Agent": "whitespace-api"})
