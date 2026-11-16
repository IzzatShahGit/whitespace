"""Alerts: the signals (pure functions), and the job that turns them into notifications.

Monthly data is faked at the source (no network): each test says what every market's
source returns, or raises.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.seed import TOWELS
from whitespace_api.core import tasks
from whitespace_api.core.config import Settings
from whitespace_api.integrations import monthly_trade as source
from whitespace_api.jobs import alerts as job
from whitespace_api.models import MonthlyTradeCache, Notification, User, Watch
from whitespace_api.notify.email import EmailMessage, LogSender, get_sender
from whitespace_api.schemas.trade import RecentMovement, RecentSupplier
from whitespace_api.services import alerts, recent
from whitespace_api.services.explain import EN_DASH

TODAY = date(2026, 11, 16)
NAMES = {"PK": "Pakistan", "BD": "Bangladesh", "CN": "China", "TR": "Türkiye"}


def settings(**values: Any) -> Settings:
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


# ---------- fake monthly data ----------
def months(end: str) -> list[str]:
    return [alerts.shift(end, -back) for back in reversed(range(30))]


def monthly(
    before: float, recent: float, last3: float | None = None, end: str = "2026-08"
) -> dict[str, float]:
    """`before` a month until a year ago, then `recent`; `last3` in the latest 3 months."""
    return {
        m: last3 if i >= 27 and last3 is not None else recent if i >= 18 else before
        for i, m in enumerate(months(end))
    }


def payload(total: dict[str, float], **partners: dict[str, float]) -> dict[str, Any]:
    return {
        "source": "eurostat",
        "currency": "EUR",
        "total": total,
        "partners": {code: {"name": NAMES[code], "values": v} for code, v in partners.items()},
    }


def moving(end: str = "2026-08") -> dict[str, Any]:
    """Imports up 30% on a year ago; Pakistan's share 5% -> 12%; China's 60% -> 52%."""
    return payload(
        total=monthly(1_000_000, 1_100_000, last3=1_300_000, end=end),
        PK=monthly(50_000, 138_000, end=end),
        CN=monthly(600_000, 600_000, end=end),
        TR=monthly(100_000, 100_000, end=end),
    )


def quiet() -> dict[str, Any]:
    return payload(
        total=monthly(1_000_000, 1_000_000),
        PK=monthly(100_000, 100_000),
        CN=monthly(500_000, 500_000),
    )


def movement(data: dict[str, Any], exporter: str = "PAK") -> RecentMovement:
    code = source.EXPORTER_CODES.get(exporter, {}).get("eurostat")
    return recent.summarise(data, exporter_code=code, fetched_at=datetime.now(UTC), stale=False)


def facts(data: dict[str, Any], exporter: str = "PAK", name: str = "Pakistan") -> alerts.Facts:
    m = movement(data, exporter)
    return alerts.measure(
        m, alerts.rivals_of(m, data, exporter), exporter=name, product="towels", market="Germany"
    )


def kinds(found: list[alerts.Alert]) -> list[str]:
    return [a.kind for a in found]


# ---------- signals ----------
def test_big_moves_become_plain_sentences_with_figures() -> None:
    imports, share, rival = alerts.alerts(facts(moving()), today=TODAY)

    assert imports.kind == "imports_up" and imports.tone == "positive"
    assert imports.title == "Towels in Germany: imports up 30%"
    assert imports.body.startswith(
        f"Germany imported €3.9M of towels in Jun{EN_DASH}Aug 2026, 30% more than a year "
        f"earlier (€3.0M in Jun{EN_DASH}Aug 2025)."
    )
    assert imports.figures["change"] == pytest.approx(0.30) and imports.month == "2026-08"

    assert share.kind == "share_up"
    assert share.title == "Towels in Germany: Pakistan's share up to 12%"
    assert share.body.startswith(
        "Pakistan supplied 12% of Germany's imports of towels in the 12 months to Aug 2026, "
        "up from 5.0% in the 12 months before."
    )

    assert rival.kind == "rival_slipping" and rival.figures["rival"] == "China"
    assert rival.title == "Towels in Germany: China is losing ground"
    assert rival.body.startswith("China, the largest supplier besides Pakistan, had 52% of")


def test_a_quiet_month_sends_nothing() -> None:
    assert alerts.alerts(facts(quiet()), today=TODAY) == []


def test_your_own_country_is_never_your_rival() -> None:
    # Pakistan leads and slips 70% -> 60%; China, next, holds 20%.
    data = payload(
        total=monthly(1_000_000, 1_000_000),
        PK=monthly(700_000, 600_000),
        CN=monthly(200_000, 200_000),
    )
    assert [s.name for s in alerts.rivals_of(movement(data), data, "PAK")] == ["China"]
    found = alerts.alerts(facts(data), today=TODAY)
    assert kinds(found) == ["share_down"] and found[0].tone == "negative"
    assert "down from 70%" in found[0].body


def test_a_country_not_selling_there_still_gets_market_alerts() -> None:
    found = alerts.alerts(facts(moving(), "BGD", "Bangladesh"), today=TODAY)
    assert kinds(found) == ["imports_up", "rival_slipping"]  # no share of its own to report


def test_a_country_the_source_has_no_code_for_has_no_rivals() -> None:
    # Its own row can't be told apart from its rivals' rows, so none are named.
    assert alerts.rivals_of(movement(moving(), "CHN"), moving(), "CHN") == []


def test_a_missing_month_skips_the_three_month_comparison() -> None:
    data = moving()
    del data["total"]["2025-07"]  # in the year-ago quarter
    assert "imports_up" not in kinds(alerts.alerts(facts(data), today=TODAY))


BASE = alerts.Facts(
    exporter="Pakistan",
    product="towels",
    market="Germany",
    currency="EUR",
    latest_month="2026-08",
    imports_12m=5e6,
    quarter=1e6,
    quarter_year_ago=1e6,
    share=0.10,
    share_before=0.10,
    rival=RecentSupplier(name="China", share_recent=0.50, share_before=0.50),
)


def rival(share_recent: float) -> RecentSupplier:
    return RecentSupplier(name="China", share_recent=share_recent, share_before=0.50)


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({}, []),
        ({"quarter": 1.21e6}, ["imports_up"]),
        ({"quarter": 1.19e6}, []),
        ({"quarter": 0.79e6}, ["imports_down"]),
        ({"quarter": 0.81e6}, []),
        ({"quarter": None, "quarter_year_ago": None}, []),
        ({"share": 0.121}, ["share_up"]),
        ({"share": 0.119}, []),
        ({"share": 0.079}, ["share_down"]),
        ({"share": 0.081}, []),
        ({"share": 0.5, "share_before": None}, []),  # under two years of data
        ({"rival": rival(0.469)}, ["rival_slipping"]),
        ({"rival": rival(0.471)}, []),
        ({"rival": rival(0.60)}, []),  # a rival gaining is not this alert
        ({"quarter": 2e6, "imports_12m": 199_000}, []),  # too small a market to judge
        ({"quarter": 2e6, "latest_month": "2026-04"}, []),  # 7 months old: trade stopped
        ({"quarter": 2e6, "latest_month": "2026-05"}, ["imports_up"]),
    ],
)
def test_thresholds(changes: dict[str, Any], expected: list[str]) -> None:
    assert kinds(alerts.alerts(replace(BASE, **changes), today=TODAY)) == expected


def test_words_for_other_markets_currencies_and_small_shares() -> None:
    us = replace(BASE, market="United States", currency="USD", quarter=1.3e6, share=0.13)
    imports, share = alerts.alerts(us, today=TODAY)
    assert imports.body.startswith("United States imported $1.3M of towels")
    assert "of United States' imports" in share.body
    small = alerts.alerts(replace(BASE, share=0.024, share_before=0.004), today=TODAY)[0]
    assert small.title.endswith("share up to 2.4%") and "up from 0.4%" in small.body


def test_months_in_words() -> None:
    assert alerts.period("2026-06", "2026-08") == f"Jun{EN_DASH}Aug 2026"
    assert alerts.period("2025-11", "2026-01") == f"Nov 2025{EN_DASH}Jan 2026"
    assert alerts.shift("2026-01", -1) == "2025-12" and alerts.shift("2025-12", 1) == "2026-01"
    assert alerts.month_name("2026-08") == "Aug 2026"


# ---------- the job ----------
@dataclass
class Sources:
    """What each market's monthly source returns (a payload) or raises."""

    data: dict[str, Any] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)


@pytest.fixture
def sources(monkeypatch: pytest.MonkeyPatch) -> Sources:
    fake = Sources()

    async def fetch(source_name: str, market: str, hs6: str, s: Settings) -> dict[str, Any]:
        fake.calls.append(market)
        outcome = fake.data[market]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(recent, "_fetch", fetch)
    return fake


@pytest.fixture
async def watchers(
    seeded: None,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, uuid.UUID]:
    """Ahmed watches towels from Pakistan into Germany, the US and Thailand; Sara watches
    Germany as Bangladesh."""
    monkeypatch.setattr(tasks, "session_factory", db_sessionmaker)
    async with db_sessionmaker() as s:
        ahmed = User(email="ahmed@example.com", full_name="Ahmed")
        sara = User(email="sara@example.com", full_name="Sara")
        s.add_all([ahmed, sara])
        await s.flush()
        for market in ("DEU", "USA", "THA"):
            s.add(Watch(user_id=ahmed.id, exporter="PAK", hs6=TOWELS, market=market))
        s.add(Watch(user_id=sara.id, exporter="BGD", hs6=TOWELS, market="DEU"))
        await s.commit()
        return {"ahmed": ahmed.id, "sara": sara.id}


async def stored(db_sessionmaker: async_sessionmaker[AsyncSession]) -> list[Notification]:
    async with db_sessionmaker() as s:
        return list((await s.scalars(select(Notification).order_by(Notification.kind))).all())


async def test_job_notifies_each_watcher_once(
    watchers: dict[str, uuid.UUID],
    sources: Sources,
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    sources.data["DEU"] = moving()
    first = await job.run(settings(), today=TODAY)
    # Thailand has no monthly source, and US data needs a Census key: only Germany.
    assert (first.pairs, first.notified, first.failed, first.unavailable) == (1, 5, 0, 0)
    assert sources.calls == ["DEU"]

    rows = await stored(db_sessionmaker)
    ahmed = [n for n in rows if n.user_id == watchers["ahmed"]]
    sara = [n for n in rows if n.user_id == watchers["sara"]]
    assert [n.kind for n in ahmed] == ["imports_up", "rival_slipping", "share_up"]
    assert [n.kind for n in sara] == ["imports_up", "rival_slipping"]  # Bangladesh: no share
    imports = ahmed[0]
    assert imports.dedupe_key == f"imports_up:PAK:{TOWELS}:DEU:2026-08"
    assert imports.link == f"/app/markets/{TOWELS}/DEU?exporter=PAK"
    assert imports.data["tone"] == "positive" and imports.data["month"] == "2026-08"
    assert sara[1].body.startswith("China, the largest supplier besides Bangladesh")

    again = await job.run(settings(), today=TODAY)
    assert again.notified == 0 and len(await stored(db_sessionmaker)) == 5
    assert sources.calls == ["DEU"]  # the rerun read the saved copy


async def test_a_new_month_is_new_news(
    watchers: dict[str, uuid.UUID],
    sources: Sources,
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    sources.data["DEU"] = moving("2026-08")
    await job.run(settings(), today=TODAY)
    async with db_sessionmaker() as s:  # the saved copy ages past its refresh time
        aged = datetime.now(UTC) - timedelta(days=30)
        await s.execute(update(MonthlyTradeCache).values(fetched_at=aged))
        await s.commit()
    sources.data["DEU"] = moving("2026-09")
    assert (await job.run(settings(), today=TODAY)).notified == 5
    months_reported = sorted({n.data["month"] for n in await stored(db_sessionmaker)})
    assert months_reported == ["2026-08", "2026-09"]


async def test_the_lock_keeps_runs_from_overlapping(
    watchers: dict[str, uuid.UUID],
    sources: Sources,
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    sources.data["DEU"] = moving()
    async with db_sessionmaker() as other_run:
        await other_run.execute(text("SELECT pg_advisory_lock(:id)"), {"id": job.LOCK_ID})
        skipped = await job.run(settings(), today=TODAY)
        await other_run.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": job.LOCK_ID})
    assert skipped.locked and skipped.pairs == 0 and sources.calls == []
    assert job.exit_code(skipped) == job.EXIT_OK
    assert (await job.run(settings(), today=TODAY)).notified == 5  # the lock was released


async def test_simultaneous_checks_cannot_duplicate(
    watchers: dict[str, uuid.UUID],
    sources: Sources,
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    sources.data["DEU"] = moving()

    async def check() -> int:  # bypasses the lock, as a second process might
        async with db_sessionmaker() as db:
            return await alerts.check_pair(
                db, market="DEU", hs6=TOWELS, settings=settings(), today=TODAY
            )

    assert sum(await asyncio.gather(check(), check())) == 5
    assert len(await stored(db_sessionmaker)) == 5


async def test_one_failing_market_does_not_stop_the_others(
    watchers: dict[str, uuid.UUID],
    sources: Sources,
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    sources.data |= {"DEU": moving(), "USA": RuntimeError("unexpected row")}
    summary = await job.run(settings(census_api_key="test-key"), today=TODAY)
    assert sorted(sources.calls) == ["DEU", "USA"]
    assert (summary.pairs, summary.failed, summary.notified) == (2, 1, 5)
    assert job.exit_code(summary) == job.EXIT_PARTIAL
    assert len(await stored(db_sessionmaker)) == 5


async def test_a_source_that_is_down_is_skipped_not_failed(
    watchers: dict[str, uuid.UUID], sources: Sources
) -> None:
    sources.data |= {"DEU": moving(), "USA": source.SourceError("timeout")}
    summary = await job.run(settings(census_api_key="test-key"), today=TODAY)
    assert (summary.unavailable, summary.failed, summary.notified) == (1, 0, 5)
    assert job.exit_code(summary) == job.EXIT_OK


async def test_watchers_see_alerts_in_their_bell(
    user: AsyncClient,
    sources: Sources,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tasks, "session_factory", db_sessionmaker)
    profile = {"exporter": "PAK", "role": "exporter", "products": [TOWELS], "current_markets": []}
    assert (await user.put("/api/v1/me/profile", json=profile)).status_code == 200
    assert (await user.post("/api/v1/watches", json={"hs6": TOWELS, "market": "DEU"})).is_success
    sources.data["DEU"] = moving()
    await job.run(settings(), today=TODAY)
    bell = (await user.get("/api/v1/notifications")).json()
    assert bell["unread"] == 3
    assert {n["title"] for n in bell["items"]} == {
        "Towels in Germany: imports up 30%",
        "Towels in Germany: Pakistan's share up to 12%",
        "Towels in Germany: China is losing ground",
    }


# ---------- email (off by default) ----------
@pytest.fixture
def outbox(monkeypatch: pytest.MonkeyPatch) -> list[EmailMessage]:
    sent: list[EmailMessage] = []

    class Recorder:
        async def send(self, message: EmailMessage) -> None:
            sent.append(message)

    monkeypatch.setattr(job, "get_sender", Recorder)
    return sent


async def test_no_email_unless_enabled(
    watchers: dict[str, uuid.UUID], sources: Sources, outbox: list[EmailMessage]
) -> None:
    sources.data["DEU"] = moving()
    assert (await job.run(settings(), today=TODAY)).notified == 5
    assert outbox == []


async def test_new_notifications_are_emailed_once_when_enabled(
    watchers: dict[str, uuid.UUID], sources: Sources, outbox: list[EmailMessage]
) -> None:
    sources.data["DEU"] = moving()
    enabled = settings(alerts_email_enabled=True, public_app_url="https://app.example")
    await job.run(enabled, today=TODAY)
    to_ahmed = [m for m in outbox if m.to == "ahmed@example.com"]
    assert len(to_ahmed) == 3 and len(outbox) == 5
    link = f"https://app.example/app/markets/{TOWELS}/DEU?exporter=PAK"
    assert all(m.text.endswith(link) for m in to_ahmed)
    assert {m.subject for m in to_ahmed} >= {"Towels in Germany: imports up 30%"}
    await job.run(enabled, today=TODAY)
    assert len(outbox) == 5  # nothing new, nothing sent


async def test_the_default_sender_sends_nothing_and_never_logs_addresses(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    sender = get_sender()
    assert isinstance(sender, LogSender)
    await sender.send(EmailMessage(to="ahmed@example.com", subject="Towels: up 30%", text="..."))
    assert "Towels: up 30%" in caplog.text and "ahmed@example.com" not in caplog.text


# ---------- running from a scheduler ----------
def test_exit_codes() -> None:
    assert job.exit_code(job.Summary(pairs=3, notified=2)) == job.EXIT_OK
    assert job.exit_code(job.Summary(pairs=3, unavailable=1)) == job.EXIT_OK
    assert job.exit_code(job.Summary(pairs=3, failed=1)) == job.EXIT_PARTIAL


def test_bad_settings_fail_without_echoing_them(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "too-short-secret")
    with pytest.raises(ValidationError) as caught:
        settings()
    assert "too-short-secret" in str(caught.value)  # pydantic's own text repeats the input
    monkeypatch.setattr(job, "get_settings", settings)
    assert job.main() == job.EXIT_FAILED
    assert "JWT_SECRET must be set" in caplog.text and "too-short-secret" not in caplog.text
