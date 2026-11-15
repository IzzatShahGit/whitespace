"""Background work that outlives the request that started it (briefs, chat replies).

Tasks are tracked so they aren't garbage-collected mid-run and so shutdown can wait for
them. Background work opens its own database session from `session_factory` (the
request's session closes when the response is sent); tests point it at their database.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.core.db import get_sessionmaker

session_factory: Callable[[], AsyncSession] = lambda: get_sessionmaker()()  # noqa: E731

_jobs: set[asyncio.Task[Any]] = set()


def spawn(job: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
    task = asyncio.create_task(job)
    _jobs.add(task)
    task.add_done_callback(_jobs.discard)
    return task


async def wait_for_jobs() -> None:
    """Wait for running background jobs (tests and graceful shutdown)."""
    while _jobs:
        await asyncio.gather(*list(_jobs), return_exceptions=True)
