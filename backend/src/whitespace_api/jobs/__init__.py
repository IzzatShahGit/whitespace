"""Periodic jobs. `scheduled_jobs()` is what the in-app scheduler runs (core/scheduler.py);
each can also be run by hand, e.g. `python -m whitespace_api.jobs.alerts`."""

from __future__ import annotations

from datetime import timedelta

from whitespace_api.core.config import Settings
from whitespace_api.core.scheduler import Job


async def _reminders(settings: Settings) -> str:
    from whitespace_api.jobs import reminders

    return await reminders.run(settings)


async def _digest(settings: Settings) -> str:
    from whitespace_api.jobs import digest

    return await digest.run(settings)


async def _alerts(settings: Settings) -> str:
    from whitespace_api.jobs import alerts

    summary = await alerts.run(settings, advisory_lock=False)
    return f"{summary.pairs} pairs, {summary.notified} new alerts, {summary.failed} failed"


async def _tenders(settings: Settings) -> str:
    from whitespace_api.jobs import tenders

    return await tenders.run(settings)


async def _sanctions(settings: Settings) -> str:
    from whitespace_api.jobs import sanctions

    return await sanctions.run(settings)


async def _bestsellers(settings: Settings) -> str:
    from whitespace_api.jobs import bestsellers

    return await bestsellers.run(settings)


def scheduled_jobs() -> list[Job]:
    return [
        Job("follow_up_reminders", every=timedelta(hours=1), lease=timedelta(minutes=10),
            run=_reminders),
        Job("weekly_digest", every=timedelta(hours=1), lease=timedelta(minutes=30), run=_digest),
        Job("tender_alerts", every=timedelta(hours=24), lease=timedelta(minutes=30),
            run=_tenders),
        Job("watchlist_alerts", every=timedelta(hours=24), lease=timedelta(minutes=45),
            run=_alerts),
        Job("sanctions_lists", every=timedelta(hours=24), lease=timedelta(minutes=30),
            run=_sanctions),
        # Hourly check; Apify runs it weekly (services/bestsellers.py decides).
        Job("amazon_bestsellers", every=timedelta(hours=1), lease=timedelta(minutes=10),
            run=_bestsellers),
    ]  # fmt: skip
