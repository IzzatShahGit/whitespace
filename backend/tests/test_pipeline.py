"""Outreach pipeline, follow-up reminders, the scheduler's leases, the weekly digest,
email verification and unsubscribe."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.seed import TOWELS
from whitespace_api.api.v1.routes import auth as auth_routes
from whitespace_api.core import scheduler, tasks
from whitespace_api.core.config import Settings, get_settings
from whitespace_api.core.ratelimit import RateLimiter
from whitespace_api.jobs import digest as digest_job
from whitespace_api.jobs import reminders
from whitespace_api.main import app
from whitespace_api.models import Notification, PipelineContact, User
from whitespace_api.notify.email import EmailMessage
from whitespace_api.services import auth as auth_service

HOLIDAY = {"hs6": TOWELS, "market": "DEU", "name": "Holiday Heimtex GmbH & Co. KG"}


async def add(user: AsyncClient, **extra: Any) -> dict[str, Any]:
    response = await user.post("/api/v1/pipeline", json=HOLIDAY | extra)
    assert response.status_code in (200, 201), response.text
    return response.json()


# --- the pipeline -------------------------------------------------------------------


async def test_adding_is_idempotent_even_at_once(user: AsyncClient) -> None:
    first = await user.post("/api/v1/pipeline", json=HOLIDAY)
    assert first.status_code == 201 and first.json()["created"] is True
    contact = first.json()["contact"]
    assert contact["stage"] == "to_contact" and contact["market_name"] == "Germany"
    # Same company under another spelling of its legal form: still one row.
    again = await user.post("/api/v1/pipeline", json=HOLIDAY | {"name": "Holiday Heimtex GmbH"})
    assert again.status_code == 200 and again.json()["contact"]["id"] == contact["id"]
    # Many saves at the same moment: one row (the unique key decides, not a read-then-write).
    results = await asyncio.gather(
        *(user.post("/api/v1/pipeline", json=HOLIDAY | {"name": "Vossen"}) for _ in range(6))
    )
    assert sorted(r.status_code for r in results) == [200] * 5 + [201]
    assert len((await user.get("/api/v1/pipeline")).json()) == 2


async def test_stages_follow_ups_and_events(user: AsyncClient) -> None:
    contact = (await add(user))["contact"]
    url = f"/api/v1/pipeline/{contact['id']}"
    emailed = (await user.patch(url, json={"version": 1, "stage": "emailed"})).json()
    assert emailed["version"] == 2 and emailed["last_contacted_at"] is not None
    assert emailed["follow_up_on"] == str(datetime.now(UTC).date() + timedelta(days=5))

    noted = (await user.patch(url, json={"version": 2, "note": "  Asked for prices  "})).json()
    assert noted["note"] == "Asked for prices" and noted["version"] == 3
    cleared = (await user.patch(url, json={"version": 3, "follow_up_on": None})).json()
    assert cleared["follow_up_on"] is None
    unchanged = (await user.patch(url, json={"version": 4, "note": "Asked for prices"})).json()
    assert unchanged["version"] == 4  # nothing changed, no new version

    won = await user.patch(url, json={"version": 4, "stage": "won", "follow_up_on": "2030-01-01"})
    assert won.json()["stage"] == "won" and won.json()["follow_up_on"] is None  # nothing to chase

    kinds = [e["kind"] for e in (await user.get(f"{url}/events")).json()]
    assert kinds == ["stage", "follow_up", "note", "stage", "added"]


async def test_stale_edits_are_refused(user: AsyncClient) -> None:
    contact = (await add(user))["contact"]
    url = f"/api/v1/pipeline/{contact['id']}"
    ok, stale = await asyncio.gather(
        user.patch(url, json={"version": 1, "stage": "emailed"}),
        user.patch(url, json={"version": 1, "stage": "lost"}),
    )
    codes = sorted([ok.status_code, stale.status_code])
    assert codes == [200, 409]  # exactly one wins; the other is told to reload
    final = (await user.get("/api/v1/pipeline")).json()[0]
    assert final["version"] == 2


async def test_validation_ownership_and_delete(user: AsyncClient) -> None:
    bad = await user.post("/api/v1/pipeline", json=HOLIDAY | {"website": "javascript:alert(1)"})
    assert bad.status_code == 422
    assert (
        await user.post("/api/v1/pipeline", json=HOLIDAY | {"market": "ZZZ"})
    ).status_code == 404
    contact = (await add(user))["contact"]
    missing = "/api/v1/pipeline/00000000-0000-0000-0000-000000000000"
    assert (await user.patch(missing, json={"version": 1})).status_code == 404
    assert (await user.delete(f"/api/v1/pipeline/{contact['id']}")).status_code == 204
    assert (await user.delete(f"/api/v1/pipeline/{contact['id']}")).status_code == 404


async def test_summary_lists_due_follow_ups(user: AsyncClient) -> None:
    contact = (await add(user))["contact"]
    yesterday = str(datetime.now(UTC).date() - timedelta(days=1))
    await user.patch(
        f"/api/v1/pipeline/{contact['id']}",
        json={"version": 1, "stage": "emailed", "follow_up_on": yesterday},
    )
    summary = (await user.get("/api/v1/pipeline/summary")).json()
    assert summary["total"] == 1 and summary["by_stage"]["emailed"] == 1
    assert [c["name"] for c in summary["due"]] == ["Holiday Heimtex GmbH & Co. KG"]
    assert summary["due"][0]["due"] is True


# --- reminders ------------------------------------------------------------------------


@pytest.fixture
def background(
    monkeypatch: pytest.MonkeyPatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    monkeypatch.setattr(tasks, "session_factory", db_sessionmaker)


async def test_reminders_are_sent_once_per_date(
    user: AsyncClient, background: None, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    contact = (await add(user))["contact"]
    today = datetime.now(UTC).date()
    await user.patch(
        f"/api/v1/pipeline/{contact['id']}",
        json={"version": 1, "stage": "emailed", "follow_up_on": str(today)},
    )
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    # Two runs at once and a rerun: still one reminder.
    await asyncio.gather(reminders.run(settings, on=today), reminders.run(settings, on=today))
    await reminders.run(settings, on=today)
    async with db_sessionmaker() as db:
        notes = list(await db.scalars(select(Notification)))
    assert len(notes) == 1 and notes[0].kind == "follow_up"
    assert notes[0].title == "Follow up with Holiday Heimtex GmbH & Co. KG"
    bell = (await user.get("/api/v1/notifications")).json()
    assert bell["items"][0]["kind"] == "follow_up"

    # A new date is a new reminder.
    await user.patch(
        f"/api/v1/pipeline/{contact['id']}",
        json={"version": 2, "follow_up_on": str(today - timedelta(days=1))},
    )
    assert await reminders.run(settings, on=today) == "1 follow-up reminders"


# --- scheduler ------------------------------------------------------------------------


async def test_leases_run_each_job_once_per_period(background: None) -> None:
    runs: list[str] = []
    gate = asyncio.Event()

    async def slow(settings: Settings) -> str:
        runs.append("slow")
        await gate.wait()
        return "done"

    async def broken(settings: Settings) -> str:
        runs.append("broken")
        raise RuntimeError("boom")

    hourly = scheduler.Job("t_slow", timedelta(hours=1), timedelta(minutes=5), slow)
    flaky = scheduler.Job("t_broken", timedelta(hours=1), timedelta(minutes=5), broken)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    first = asyncio.create_task(scheduler.run_due([hourly], settings))
    await asyncio.sleep(0.2)
    assert await scheduler.run_due([hourly], settings) == []  # held by the first
    gate.set()
    assert await first == ["t_slow"]
    assert await scheduler.run_due([hourly], settings) == []  # done; not due for an hour

    assert await scheduler.run_due([flaky], settings) == ["t_broken"]
    assert await scheduler.run_due([flaky], settings) == ["t_broken"]  # failed: free to retry
    assert runs == ["slow", "broken", "broken"]


# --- digest, verification, unsubscribe ----------------------------------------------


class Outbox:
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.sent.append(message)


@pytest.fixture
def mail(monkeypatch: pytest.MonkeyPatch, background: None) -> Iterator[Outbox]:
    box = Outbox()
    monkeypatch.setattr(auth_service, "get_sender", lambda _s: box)
    monkeypatch.setattr(digest_job, "get_sender", lambda _s: box)
    monkeypatch.setattr(auth_routes, "_reset_limit", RateLimiter(per_minute=1000))
    app.dependency_overrides[get_settings] = lambda: MAIL_SETTINGS
    yield box
    app.dependency_overrides.pop(get_settings, None)


MAIL_SETTINGS = Settings(
    _env_file=None,  # type: ignore[call-arg]
    smtp_user="whitespace@example.com",
    smtp_password=SecretStr("app-pass"),
)
MONDAY = datetime(2026, 11, 23, 9, 0, tzinfo=UTC)


async def test_digest_needs_a_verified_address(
    user: AsyncClient, mail: Outbox, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    on = await user.post("/api/v1/auth/digest", json={"enabled": True})
    assert on.json() == {"digest_enabled": False, "verification_sent": True}
    await tasks.wait_for_jobs()
    link = re.search(r"verify-email\?token=(\S+)", mail.sent[-1].text)
    assert link and mail.sent[-1].subject.startswith("Confirm")

    # Nothing goes out before the address is confirmed.
    contact = (await add(user))["contact"]
    await user.patch(
        f"/api/v1/pipeline/{contact['id']}",
        json={"version": 1, "stage": "emailed", "follow_up_on": "2026-11-20"},
    )
    assert (await digest_job.run(MAIL_SETTINGS, now=MONDAY)).startswith("2026-W48: 0 sent")

    verified = await user.post("/api/v1/auth/verify-email", json={"token": link.group(1)})
    assert verified.json()["email_verified"] is True and verified.json()["digest_enabled"] is True
    again = await user.post("/api/v1/auth/verify-email", json={"token": link.group(1)})
    assert again.status_code == 400  # one use

    mail.sent.clear()
    # Two overlapping runs and a rerun send one email.
    await asyncio.gather(
        digest_job.run(MAIL_SETTINGS, now=MONDAY), digest_job.run(MAIL_SETTINGS, now=MONDAY)
    )
    await digest_job.run(MAIL_SETTINGS, now=MONDAY)
    assert len(mail.sent) == 1
    email = mail.sent[0]
    assert email.subject == "Your Whitespace week: 1 follow-up due"
    assert "Holiday Heimtex GmbH & Co. KG (Germany): emailed, due 20 Nov" in email.text
    assert "List-Unsubscribe" in email.headers

    # The link in the email stops it; a forged one doesn't.
    found = re.search(r"unsubscribe\?u=(\S+)&t=(\S+)", email.text)
    assert found
    forged = await user.post("/api/v1/auth/unsubscribe", json={"u": found.group(1), "t": "0" * 32})
    assert forged.status_code == 400
    ok = await user.post(
        "/api/v1/auth/unsubscribe", json={"u": found.group(1), "t": found.group(2)}
    )
    assert ok.status_code == 204
    assert (await user.get("/api/v1/auth/me")).json()["digest_enabled"] is False


async def test_digest_timing_and_quiet_weeks(
    user: AsyncClient, mail: Outbox, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    async with db_sessionmaker() as db:
        await db.execute(update(User).values(email_verified=True, digest_enabled=True))
        await db.commit()
    early_monday = datetime(2026, 11, 23, 5, 0, tzinfo=UTC)
    assert await digest_job.run(MAIL_SETTINGS, now=early_monday) == "not digest time yet"
    # Nothing to report: no email, and the week counts as handled.
    assert "0 sent, 1 with nothing new" in await digest_job.run(MAIL_SETTINGS, now=MONDAY)
    assert mail.sent == []
    async with db_sessionmaker() as db:
        assert await db.scalar(select(func.count()).select_from(PipelineContact)) == 0


async def test_failed_sends_are_retried(
    user: AsyncClient, mail: Outbox, monkeypatch: pytest.MonkeyPatch,
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:  # fmt: skip
    async with db_sessionmaker() as db:
        await db.execute(update(User).values(email_verified=True, digest_enabled=True))
        await db.commit()
    contact = (await add(user))["contact"]
    await user.patch(
        f"/api/v1/pipeline/{contact['id']}",
        json={"version": 1, "stage": "emailed", "follow_up_on": "2026-11-20"},
    )

    class Down:
        async def send(self, message: EmailMessage) -> None:
            raise ConnectionError("smtp down")

    monkeypatch.setattr(digest_job, "get_sender", lambda _s: Down())
    assert "1 failed" in await digest_job.run(MAIL_SETTINGS, now=MONDAY)
    monkeypatch.setattr(digest_job, "get_sender", lambda _s: mail)
    assert "1 sent" in await digest_job.run(MAIL_SETTINGS, now=MONDAY)
    assert len(mail.sent) == 1


async def test_digest_off_without_email(user: AsyncClient) -> None:
    response = await user.post("/api/v1/auth/digest", json={"enabled": True})
    assert response.status_code == 503
    off = await user.post("/api/v1/auth/digest", json={"enabled": False})
    assert off.json() == {"digest_enabled": False, "verification_sent": False}
    assert await digest_job.run(Settings(_env_file=None)) == "email isn't set up"  # type: ignore[call-arg]


def test_digest_period_is_the_iso_week() -> None:
    assert digest_job.period(datetime(2026, 1, 1, tzinfo=UTC)) == "2026-W01"
    assert digest_job.period(datetime(2027, 1, 1, tzinfo=UTC)) == "2026-W53"
    assert date(2026, 11, 23).weekday() == 0
