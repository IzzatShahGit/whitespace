"""Send the weekly digest to users who opted in and verified their address.

Each (user, ISO week) is claimed in `email_sends` before the email is built, so reruns
and overlapping runs send it at most once; if sending fails the claim is released and
the next run retries. Runs from the digest day/hour until the end of that ISO week.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from whitespace_api.core import tasks
from whitespace_api.core.config import Settings
from whitespace_api.models.jobs import EmailSend
from whitespace_api.models.user import User
from whitespace_api.notify.email import get_sender
from whitespace_api.services import digest as service

log = logging.getLogger(__name__)
KIND = "digest"
MAX_PER_RUN = 200  # stays well inside a Gmail account's daily sending limit


def period(now: datetime) -> str:
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"


def is_digest_time(now: datetime, settings: Settings) -> bool:
    day = now.weekday()
    return day > settings.digest_weekday or (
        day == settings.digest_weekday and now.hour >= settings.digest_hour_utc
    )


async def run(settings: Settings, *, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    if not settings.email_enabled:
        return "email isn't set up"
    if not is_digest_time(now, settings):
        return "not digest time yet"
    week = period(now)
    sender = get_sender(settings)
    sent = skipped = failed = 0
    async with tasks.session_factory() as db:
        already = select(EmailSend.user_id).where(EmailSend.kind == KIND, EmailSend.period == week)
        # Plain ids: a rollback after a failed send can't leave stale objects behind.
        user_ids = list(
            await db.scalars(
                select(User.id)
                .where(
                    User.digest_enabled.is_(True),
                    User.email_verified.is_(True),
                    User.is_active.is_(True),
                    User.id.not_in(already),
                )
                .order_by(User.id)
                .limit(MAX_PER_RUN)
            )
        )
        for user_id in user_ids:
            claimed = await db.scalar(
                insert(EmailSend)
                .values(user_id=user_id, kind=KIND, period=week)
                .on_conflict_do_nothing()
                .returning(EmailSend.user_id)
            )
            await db.commit()
            if claimed is None:
                continue  # another run has it
            try:
                user = await db.get(User, user_id, populate_existing=True)
                if user is None or not user.digest_enabled:
                    skipped += 1
                    continue
                digest = await service.build(db, user, settings, now.date())
                if digest is None:
                    skipped += 1
                    continue
                await sender.send(service.message(user, digest, settings))
                sent += 1
            except Exception as exc:
                failed += 1
                log.warning("Digest for one user failed: %s", type(exc).__name__)
                await db.rollback()
                await db.execute(
                    delete(EmailSend).where(
                        EmailSend.user_id == user_id,
                        EmailSend.kind == KIND,
                        EmailSend.period == week,
                    )
                )
                await db.commit()
    return f"{week}: {sent} sent, {skipped} with nothing new, {failed} failed"
