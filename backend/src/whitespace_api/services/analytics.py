"""First-party usage analytics, kept small and anonymous.

- Page views and a few browser-only actions arrive at POST /events and are counted per
  day and page pattern (`/app/markets/[hs6]/[country]`, never ids or query strings).
- Unique visitors: a hash of (secret, day, address, browser) cut to 16 hex characters,
  stored per day only. The same person gets an unrelated hash tomorrow; addresses are
  never stored.
- Sign-ups, briefs, lead searches, chat and watches are counted from their own tables.
- Visits (origin, device, pages, time) come from services/visits.py.
- Test, demo and admin accounts are left out of the user numbers and of visit stats.
- Rows older than `analytics_keep_days` (visits: `visit_keep_days`) are pruned whenever
  the summary is read.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, Date, cast, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.core.config import Settings
from whitespace_api.models.analytics import AnalyticsDaily, AnalyticsVisitor, Visit
from whitespace_api.models.brief import MarketBrief
from whitespace_api.models.lead import TradeLeads
from whitespace_api.models.usage import UsageCounter
from whitespace_api.models.user import User, UserActivityDay
from whitespace_api.models.watch import Watch
from whitespace_api.schemas.analytics import AdminStats, Count, DayStats, Totals, VisitSummary
from whitespace_api.services import visits as visits_service

BOT = re.compile(r"bot|crawl|spider|slurp|preview|monitor|curl|wget|python|headless", re.I)
PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^\d{6}$"), "[hs6]"),
    (re.compile(r"^[A-Z]{3}$"), "[country]"),
    (re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I), "[id]"),
    (re.compile(r"^[A-Za-z0-9_-]{24,}$"), "[id]"),
]
MAX_PATH = 120
TOP_PAGES = 15


def is_bot(user_agent: str) -> bool:
    return not user_agent or bool(BOT.search(user_agent))


def page_pattern(path: str | None) -> str:
    """'/app/markets/630260/DEU?tab=prices' -> '/app/markets/[hs6]/[country]'."""
    if not path or not path.startswith("/"):
        return ""
    path = path.split("?", 1)[0].split("#", 1)[0]
    parts = []
    for part in path.strip("/").split("/"):
        for pattern, name in PATTERNS:
            if pattern.match(part):
                part = name
                break
        parts.append(part)
    return ("/" + "/".join(p for p in parts if p))[:MAX_PATH]


def visitor_id(secret: str, day: date, address: str, user_agent: str) -> str:
    return hashlib.sha256(f"{secret}|{day}|{address}|{user_agent}".encode()).hexdigest()[:16]


def today() -> date:
    return datetime.now(UTC).date()


async def record(db: AsyncSession, *, event: str, path: str = "", visitor: str | None) -> None:
    day = today()
    count = insert(AnalyticsDaily).values(day=day, event=event, path=path, count=1)
    await db.execute(
        count.on_conflict_do_update(
            index_elements=["day", "event", "path"],
            set_={"count": AnalyticsDaily.count + 1},
        )
    )
    if visitor is not None:
        seen = insert(AnalyticsVisitor).values(day=day, visitor=visitor)
        await db.execute(seen.on_conflict_do_nothing())
    await db.commit()


def internal_users(settings: Settings) -> ColumnElement[bool]:
    """Test, demo and admin accounts: kept, but out of the real-user numbers."""
    admins = [e.strip().lower() for e in settings.admin_emails if e.strip()]
    return or_(User.is_test.is_(True), User.email.in_(admins))


def real_visits(settings: Settings) -> ColumnElement[bool]:
    """Visits that aren't by a test, demo or admin account (anonymous ones count)."""
    return or_(
        Visit.user_id.is_(None),
        Visit.user_id.not_in(select(User.id).where(internal_users(settings))),
    )


async def _counts(db: AsyncSession, column: Any, *where: Any, limit: int = 10) -> list[Count]:
    rows = await db.execute(
        select(column, func.count()).where(*where).group_by(column).order_by(func.count().desc())
    )
    return [Count(name=name or "", count=int(n)) for name, n in rows.all()[:limit]]


async def _visit_summary(db: AsyncSession, settings: Settings, start: datetime) -> VisitSummary:
    now = datetime.now(UTC)
    real = real_visits(settings)
    period = (Visit.started_at >= start, real)
    row = (
        await db.execute(
            select(
                func.count(),
                func.count(Visit.user_id),
                func.coalesce(func.avg(Visit.engaged_seconds), 0),
                func.coalesce(func.avg(Visit.pages), 0),
                func.count().filter(Visit.pages == 1, Visit.engaged_seconds < 10),
            ).where(*period)
        )
    ).one()
    total = int(row[0])
    live = await db.scalar(
        select(func.count()).where(Visit.last_seen_at >= now - timedelta(minutes=5), real)
    )
    return VisitSummary(
        live_now=int(live or 0),
        visits=total,
        signed_in=int(row[1]),
        avg_seconds=round(float(row[2])),
        avg_pages=round(float(row[3]), 1),
        bounce_rate=round(int(row[4]) / total, 3) if total else 0.0,
        countries=await _counts(db, Visit.country, *period, limit=15),
        sources=await _counts(db, Visit.source, *period),
        devices=await _counts(db, Visit.device, *period),
        browsers=await _counts(db, Visit.browser, *period, limit=6),
        landing=await _counts(db, Visit.landing, *period),
    )


async def summary(db: AsyncSession, settings: Settings, days: int = 30) -> AdminStats:
    until = today()
    since = until - timedelta(days=days - 1)
    start = datetime.combine(since, datetime.min.time(), tzinfo=UTC)
    keep = until - timedelta(days=settings.analytics_keep_days)
    await db.execute(delete(AnalyticsDaily).where(AnalyticsDaily.day < keep))
    await db.execute(delete(AnalyticsVisitor).where(AnalyticsVisitor.day < keep))
    await db.execute(delete(UserActivityDay).where(UserActivityDay.day < keep))
    await visits_service.prune(db, settings.visit_keep_days, datetime.now(UTC))
    await db.commit()

    internal = internal_users(settings)
    real_ids = select(User.id).where(~internal)
    views = dict(
        (
            await db.execute(
                select(AnalyticsDaily.day, func.sum(AnalyticsDaily.count))
                .where(AnalyticsDaily.event == "page_view", AnalyticsDaily.day >= since)
                .group_by(AnalyticsDaily.day)
            )
        ).all()
    )
    visitors = dict(
        (
            await db.execute(
                select(AnalyticsVisitor.day, func.count())
                .where(AnalyticsVisitor.day >= since)
                .group_by(AnalyticsVisitor.day)
            )
        ).all()
    )
    joined = cast(User.created_at, Date)
    sign_ups = dict(
        (
            await db.execute(
                select(joined, func.count()).where(joined >= since, ~internal).group_by(joined)
            )
        ).all()
    )
    active = dict(
        (
            await db.execute(
                select(UserActivityDay.day, func.count())
                .where(UserActivityDay.day >= since, UserActivityDay.user_id.in_(real_ids))
                .group_by(UserActivityDay.day)
            )
        ).all()
    )
    started = cast(Visit.started_at, Date)
    visits_per_day = dict(
        (
            await db.execute(
                select(started, func.count())
                .where(Visit.started_at >= start, real_visits(settings))
                .group_by(started)
            )
        ).all()
    )
    series = [
        DayStats(
            day=d,
            page_views=int(views.get(d, 0)),
            visitors=visitors.get(d, 0),
            sign_ups=sign_ups.get(d, 0),
            active_users=active.get(d, 0),
            visits=visits_per_day.get(d, 0),
        )
        for d in (since + timedelta(days=i) for i in range(days))
    ]

    pages = await db.execute(
        select(AnalyticsDaily.path, func.sum(AnalyticsDaily.count).label("n"))
        .where(AnalyticsDaily.event == "page_view", AnalyticsDaily.day >= since)
        .group_by(AnalyticsDaily.path)
        .order_by(func.sum(AnalyticsDaily.count).desc())
        .limit(TOP_PAGES)
    )
    clicks = await db.execute(
        select(AnalyticsDaily.event, func.sum(AnalyticsDaily.count))
        .where(AnalyticsDaily.event != "page_view", AnalyticsDaily.day >= since)
        .group_by(AnalyticsDaily.event)
    )
    chats = await db.scalar(
        select(func.coalesce(func.sum(UsageCounter.count), 0)).where(
            UsageCounter.kind == "chat", UsageCounter.day >= since
        )
    )
    made = {
        "AI briefs written": MarketBrief.created_at,
        "Company searches": TradeLeads.created_at,
        "Markets watched": Watch.created_at,
    }
    actions = [Count(name="Questions to the guide", count=int(chats or 0))]
    for name, column in made.items():
        n = await db.scalar(select(func.count()).where(column >= start))
        actions.append(Count(name=name, count=int(n or 0)))
    labels = {
        "deal_sheet_print": "Deal sheets printed",
        "deal_sheet_copy_link": "Deal sheet links copied",
        "email_draft_open": "Emails to companies opened",
        "intro_copy": "Intro emails copied",
    }
    actions += [Count(name=labels.get(e, e), count=int(n)) for e, n in clicks.all()]

    users = await db.scalar(select(func.count()).select_from(User).where(~internal))
    test_users = await db.scalar(select(func.count()).select_from(User).where(internal))

    async def active_since(d: date) -> int:
        n = await db.scalar(
            select(func.count(func.distinct(UserActivityDay.user_id))).where(
                UserActivityDay.day >= d, UserActivityDay.user_id.in_(real_ids)
            )
        )
        return int(n or 0)

    unique = await db.scalar(
        select(func.count(func.distinct(AnalyticsVisitor.visitor))).where(
            AnalyticsVisitor.day >= since
        )
    )
    return AdminStats(
        since=since,
        until=until,
        totals=Totals(
            users=int(users or 0),
            test_users=int(test_users or 0),
            active_7d=await active_since(until - timedelta(days=6)),
            active_30d=await active_since(since),
            sign_ups=sum(d.sign_ups for d in series),
            visitors=int(unique or 0),
            page_views=sum(d.page_views for d in series),
        ),
        days=series,
        top_pages=[Count(name=p or "(other)", count=int(n)) for p, n in pages.all()],
        actions=actions,
        visits=await _visit_summary(db, settings, start),
    )
