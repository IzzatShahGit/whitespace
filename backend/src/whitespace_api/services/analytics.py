"""First-party usage analytics, kept small and anonymous.

- Page views and a few browser-only actions arrive at POST /events and are counted per
  day and page pattern (`/app/markets/[hs6]/[country]`, never ids or query strings).
- Unique visitors: a hash of (secret, day, address, browser) cut to 16 hex characters,
  stored per day only. The same person gets an unrelated hash tomorrow; addresses are
  never stored.
- Sign-ups, briefs, lead searches, chat and watches are counted from their own tables.
- Rows older than `analytics_keep_days` are pruned whenever the summary is read.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import Date, cast, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.core.config import Settings
from whitespace_api.models.analytics import AnalyticsDaily, AnalyticsVisitor
from whitespace_api.models.brief import MarketBrief
from whitespace_api.models.lead import TradeLeads
from whitespace_api.models.usage import UsageCounter
from whitespace_api.models.user import User
from whitespace_api.models.watch import Watch
from whitespace_api.schemas.analytics import AdminStats, Count, DayStats, Totals

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


async def _per_day(db: AsyncSession, column: object, since: date) -> dict[date, int]:
    day = cast(column, Date)
    rows = await db.execute(select(day, func.count()).where(day >= since).group_by(day))
    return dict(rows.all())


async def summary(db: AsyncSession, settings: Settings, days: int = 30) -> AdminStats:
    until = today()
    since = until - timedelta(days=days - 1)
    keep = until - timedelta(days=settings.analytics_keep_days)
    await db.execute(delete(AnalyticsDaily).where(AnalyticsDaily.day < keep))
    await db.execute(delete(AnalyticsVisitor).where(AnalyticsVisitor.day < keep))
    await db.commit()

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
    sign_ups = await _per_day(db, User.created_at, since)
    series = [
        DayStats(
            day=d,
            page_views=int(views.get(d, 0)),
            visitors=visitors.get(d, 0),
            sign_ups=sign_ups.get(d, 0),
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
    start = datetime.combine(since, datetime.min.time(), tzinfo=UTC)
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

    users = await db.scalar(select(func.count()).select_from(User))
    active = await db.scalar(
        select(func.count()).where(User.last_login_at >= datetime.now(UTC) - timedelta(days=7))
    )
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
            active_7d=int(active or 0),
            sign_ups=sum(d.sign_ups for d in series),
            visitors=int(unique or 0),
            page_views=sum(d.page_views for d in series),
        ),
        days=series,
        top_pages=[Count(name=p or "(other)", count=int(n)) for p, n in pages.all()],
        actions=actions,
    )
