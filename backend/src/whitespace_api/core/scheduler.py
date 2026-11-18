"""Runs periodic jobs inside the API process: follow-up reminders, the weekly digest,
watchlist alerts.

Every TICK each job is offered to whoever can take its lease: one conditional UPDATE on
`job_leases` that succeeds only if nobody holds the lease and the job is due. So with
one process or many, each job runs once per period; a process that dies mid-run frees
the lease when `locked_until` passes. A job is cancelled before its lease runs out, so
two runs never overlap. Leases are plain rows, which works behind a connection pooler.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, or_, update
from sqlalchemy.dialects.postgresql import insert

from whitespace_api.core import tasks
from whitespace_api.core.config import Settings
from whitespace_api.models.jobs import JobLease

log = logging.getLogger(__name__)

TICK_SECONDS = 300
FIRST_TICK_SECONDS = 60  # let the app finish starting


@dataclass(frozen=True)
class Job:
    name: str
    every: timedelta
    lease: timedelta  # the longest one run may take
    run: Callable[[Settings], Awaitable[str]]  # returns a one-line summary for the log


async def acquire(job: Job) -> uuid.UUID | None:
    holder = uuid.uuid4()
    async with tasks.session_factory() as db:
        await db.execute(insert(JobLease).values(name=job.name).on_conflict_do_nothing())
        taken = await db.scalar(
            update(JobLease)
            .where(
                JobLease.name == job.name,
                or_(JobLease.locked_until.is_(None), JobLease.locked_until < func.now()),
                or_(
                    JobLease.last_ok_at.is_(None),
                    JobLease.last_ok_at < func.now() - job.every,
                ),
            )
            .values(holder=holder, locked_until=func.now() + job.lease)
            .returning(JobLease.holder)
        )
        await db.commit()
    return taken


async def release(job: Job, holder: uuid.UUID, *, ok: bool, error: str | None = None) -> None:
    values: dict[str, object] = {"locked_until": func.now(), "last_error": error}
    if ok:
        values["last_ok_at"] = func.now()
    async with tasks.session_factory() as db:
        await db.execute(
            update(JobLease)
            .where(JobLease.name == job.name, JobLease.holder == holder)
            .values(**values)
        )
        await db.commit()


async def run_due(jobs: list[Job], settings: Settings) -> list[str]:
    """Run every job that's due and free. Returns the names that ran."""
    ran: list[str] = []
    for job in jobs:
        try:
            holder = await acquire(job)
        except Exception:
            log.exception("Scheduler couldn't check job %s", job.name)
            continue
        if holder is None:
            continue
        ran.append(job.name)
        try:
            # Stop before the lease ends, so no second run can start alongside.
            limit = job.lease.total_seconds() * 0.9
            summary = await asyncio.wait_for(job.run(settings), timeout=limit)
        except Exception as exc:
            log.exception("Job %s failed", job.name)
            await release(job, holder, ok=False, error=f"{type(exc).__name__}"[:300])
        else:
            log.info("Job %s: %s", job.name, summary)
            await release(job, holder, ok=True)
    return ran


async def _loop(jobs: list[Job], settings: Settings) -> None:
    await asyncio.sleep(FIRST_TICK_SECONDS)
    while True:
        await run_due(jobs, settings)
        await asyncio.sleep(TICK_SECONDS)


_task: asyncio.Task[None] | None = None


def start(jobs: list[Job], settings: Settings) -> None:
    global _task
    if _task is None and settings.scheduler_enabled:
        _task = asyncio.create_task(_loop(jobs, settings))


async def stop() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _task
        _task = None
