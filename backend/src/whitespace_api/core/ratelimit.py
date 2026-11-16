"""A small in-process rate limiter for public (signed-out) endpoints.

Sliding window per client key, bounded memory (oldest keys evicted). Per process, so
with several API instances the effective limit is a multiple; a shared store (Redis)
can replace it later behind the same interface.
"""

from __future__ import annotations

import time
from collections import OrderedDict, deque

from fastapi import HTTPException, Request, status


class RateLimiter:
    def __init__(self, *, per_minute: int, max_keys: int = 10_000) -> None:
        self.per_minute = per_minute
        self.max_keys = max_keys
        self._hits: OrderedDict[str, deque[float]] = OrderedDict()

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        hits = self._hits.pop(key, None) or deque()
        while hits and now - hits[0] >= 60:
            hits.popleft()
        allowed = len(hits) < self.per_minute
        if allowed:
            hits.append(now)
        self._hits[key] = hits  # most recent last
        while len(self._hits) > self.max_keys:
            self._hits.popitem(last=False)
        return allowed


def client_key(request: Request) -> str:
    """The caller's address: first X-Forwarded-For hop (set by our own web proxy), else the peer."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def limit(limiter: RateLimiter, request: Request) -> None:
    if not limiter.allow(client_key(request)):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests. Please wait a minute."
        )
