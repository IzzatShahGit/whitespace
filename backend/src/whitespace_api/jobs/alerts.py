"""Check every watched product-market for news in its monthly customs data.

    make alerts        (or: cd backend && python -m whitespace_api.jobs.alerts)

Built to run from cron or any scheduler, as often as you like (daily is plenty):
- A Postgres advisory lock keeps runs from overlapping: a second run exits at once.
- Monthly data comes through the shared cache, so a source is only asked again once
  its saved copy is older than `monthly_cache_days`.
- The database deduplicates notifications, so rerunning never repeats one.
- One market failing never stops the others; each is logged.

Exit codes: 0 done (or another run was already going), 1 some markets failed,
2 the run itself failed (bad settings, database unreachable).
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime

from pydantic import ValidationError
from sqlalchemy import text

from whitespace_api.core import tasks
from whitespace_api.core.config import Settings, get_settings
from whitespace_api.core.db import get_engine
from whitespace_api.core.http import http_client
from whitespace_api.core.logging import configure_logging
from whitespace_api.notify.email import Sender, get_sender
from whitespace_api.repositories import watches as watch_repo
from whitespace_api.services import alerts
from whitespace_api.services import recent as recent_service

log = logging.getLogger(__name__)

# Identifies this job's advisory lock: any fixed number no other lock in the app uses.
LOCK_ID = 7_310_001
CONCURRENCY = 3  # markets checked at once: gentle on the free data sources

EXIT_OK = 0
EXIT_PARTIAL = 1
EXIT_FAILED = 2


@dataclass
class Summary:
    locked: bool = False  # another run held the lock, so this one did nothing
    pairs: int = 0
    notified: int = 0  # new notifications
    unavailable: int = 0  # source down with nothing saved, or no data for the product
    failed: int = 0  # unexpected errors, logged with a traceback


async def run(settings: Settings, *, today: date | None = None) -> Summary:
    """One run, unless another holds the lock."""
    async with tasks.session_factory() as lock_session:
        # A session-level lock on a connection in autocommit mode: held for the whole run
        # without keeping a transaction open, and freed by Postgres if the process dies.
        conn = await lock_session.connection(execution_options={"isolation_level": "AUTOCOMMIT"})
        if not await conn.scalar(text("SELECT pg_try_advisory_lock(:id)"), {"id": LOCK_ID}):
            log.info("Alerts: another run is in progress; nothing to do")
            return Summary(locked=True)
        try:
            sender = get_sender() if settings.alerts_email_enabled else None
            return await _check_all(settings, today or datetime.now(UTC).date(), sender)
        finally:
            await conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": LOCK_ID})


async def _check_all(settings: Settings, today: date, sender: Sender | None) -> Summary:
    started = time.monotonic()
    async with tasks.session_factory() as db:
        pairs = await watch_repo.watched_pairs(db, alerts.monthly_markets(settings))
    slots = asyncio.Semaphore(CONCURRENCY)

    async def check(market: str, hs6: str) -> int:
        async with slots, tasks.session_factory() as db:  # a session per market
            return await alerts.check_pair(
                db, market=market, hs6=hs6, settings=settings, today=today, sender=sender
            )

    # return_exceptions: one market's failure is collected, never stops the others.
    results = await asyncio.gather(*(check(*pair) for pair in pairs), return_exceptions=True)
    summary = Summary(pairs=len(pairs))
    for (market, hs6), result in zip(pairs, results, strict=True):
        if isinstance(result, recent_service.UnavailableError):
            summary.unavailable += 1
            # Its message is safe to log; its cause may hold a source URL with an API key.
            log.warning("Alerts: %s %s skipped: %s", market, hs6, result)
        elif isinstance(result, BaseException):
            summary.failed += 1
            log.error("Alerts: checking %s %s failed", market, hs6, exc_info=result)
        else:
            summary.notified += result
    log.info(
        "Alerts: %d markets checked in %.1fs: %d new notifications, %d unavailable, %d failed",
        summary.pairs, time.monotonic() - started,
        summary.notified, summary.unavailable, summary.failed,
    )  # fmt: skip
    return summary


def exit_code(summary: Summary) -> int:
    return EXIT_PARTIAL if summary.failed else EXIT_OK


async def _main(settings: Settings) -> int:
    try:
        return exit_code(await run(settings))
    except Exception:
        log.exception("Alerts: the run failed")
        return EXIT_FAILED
    finally:
        await http_client().aclose()
        await get_engine().dispose()


def main() -> int:
    try:
        settings = get_settings()
    except ValidationError as exc:
        configure_logging("INFO")
        # Only the messages: pydantic's full error text repeats the input, secrets included.
        log.error("Alerts: invalid settings: %s", "; ".join(e["msg"] for e in exc.errors()))
        return EXIT_FAILED
    configure_logging(settings.log_level)
    return asyncio.run(_main(settings))


if __name__ == "__main__":
    raise SystemExit(main())
