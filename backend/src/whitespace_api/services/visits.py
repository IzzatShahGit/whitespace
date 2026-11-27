"""Visits: who is looking at the site, from where, on what, and for how long.

A visit is a run of page views from one visitor with gaps under 30 minutes. Visitors
are the day-scoped hash from `analytics.visitor_id` (no cookies, no stored addresses),
so an anonymous person is a new visitor each day; signed-in people are linked to their
account, which is what ties their visits together over time.

Time spent is "engaged" time: the browser counts seconds while the tab is visible and
the person has moved, typed or scrolled in the last two minutes, and reports it here.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.models.analytics import Visit, VisitPage

VISIT_GAP = timedelta(minutes=30)
MAX_ENGAGE = 600  # seconds one report may add (the browser reports at least every minute)
MAX_PAGES_KEPT = 200  # pages recorded per visit; later ones still count, without a row
_ID = re.compile(
    r"^([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[A-Za-z0-9_-]{24,})$", re.I
)

# Hosts whose referrals are really our own pages (e.g. coming back from Google sign-in).
_INTERNAL = {"accounts.google.com", "localhost", "127.0.0.1"}
_SOURCES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(p), name)
    for p, name in [
        (r"(^|\.)google\.[a-z.]+$", "Google"),
        (r"(^|\.)bing\.com$", "Bing"),
        (r"(^|\.)duckduckgo\.com$", "DuckDuckGo"),
        (r"(^|\.)yahoo\.[a-z.]+$", "Yahoo"),
        (r"(^|\.)yandex\.[a-z.]+$", "Yandex"),
        (r"(^|\.)(linkedin\.com|lnkd\.in)$", "LinkedIn"),
        (r"(^|\.)(facebook\.com|fb\.com|fb\.me)$", "Facebook"),
        (r"(^|\.)instagram\.com$", "Instagram"),
        (r"(^|\.)(t\.co|twitter\.com|x\.com)$", "X (Twitter)"),
        (r"(^|\.)reddit\.com$", "Reddit"),
        (r"(^|\.)(youtube\.com|youtu\.be)$", "YouTube"),
        (r"(^|\.)(whatsapp\.com|wa\.me)$", "WhatsApp"),
        (r"(^|\.)(t\.me|telegram\.org)$", "Telegram"),
        (r"(^|\.)github\.com$", "GitHub"),
        (r"(^|\.)(chatgpt\.com|openai\.com)$", "ChatGPT"),
        (r"(^|\.)perplexity\.ai$", "Perplexity"),
        (r"(^|\.)claude\.ai$", "Claude"),
        (r"(^|\.)(mail\.google\.com|outlook\.live\.com|outlook\.office\.com)$", "Email"),
    ]
]
_UTM_NAMES = {name.lower().split(" ")[0]: name for _, name in _SOURCES}


def journey_path(path: str | None) -> str:
    """'/app/markets/630260/DEU?tab=prices' -> '/app/markets/630260/DEU'.

    Product and country codes stay (they say what someone looked at); record ids
    (conversations, contacts) become [id]; query strings go.
    """
    if not path or not path.startswith("/"):
        return "/"
    path = path.split("?", 1)[0].split("#", 1)[0]
    parts = ["[id]" if _ID.match(p) else p for p in path.strip("/").split("/") if p]
    return ("/" + "/".join(parts))[:120]


def referrer_host(referrer: str | None, own_host: str) -> str | None:
    """The referring site's host, or None for none / our own site."""
    if not referrer:
        return None
    try:
        host = (urlsplit(referrer).hostname or "").lower()
    except ValueError:
        return None
    host = host.removeprefix("www.")
    own = own_host.split(":", 1)[0].lower().removeprefix("www.")
    if not host or host == own or host in _INTERNAL:
        return None
    return host[:120]


def source_of(host: str | None, utm_source: str | None) -> str:
    """Where a visit came from, as a person would say it: 'Google', 'LinkedIn', 'Direct'."""
    if utm_source:
        tag = re.sub(r"[^a-z0-9._ -]", "", utm_source.strip().lower())[:60]
        if tag:
            return _UTM_NAMES.get(tag.split(".")[0], tag)
    if not host:
        return "Direct"
    for pattern, name in _SOURCES:
        if pattern.search(host):
            return name
    return host[:60]


def device_of(agent: str) -> str:
    if re.search(r"iPad|Tablet|PlayBook|Silk|Android(?!.*Mobile)", agent):
        return "tablet"
    if re.search(r"Mobi|iPhone|iPod|Android|Opera Mini|IEMobile", agent):
        return "mobile"
    return "desktop"


def browser_of(agent: str) -> str:
    for pattern, name in (
        (r"Edg(e|A|iOS)?/", "Edge"),
        (r"OPR/|Opera", "Opera"),
        (r"SamsungBrowser/", "Samsung Internet"),
        (r"UCBrowser/", "UC Browser"),
        (r"Firefox/|FxiOS/", "Firefox"),
        (r"Chrome/|CriOS/", "Chrome"),
        (r"Safari/", "Safari"),
    ):
        if re.search(pattern, agent):
            return name
    return "Other"


def os_of(agent: str) -> str:
    for pattern, name in (
        (r"Windows", "Windows"),
        (r"Android", "Android"),
        (r"iPhone|iPad|iPod", "iOS"),
        (r"CrOS", "ChromeOS"),
        (r"Mac OS X|Macintosh", "macOS"),
        (r"Linux", "Linux"),
    ):
        if re.search(pattern, agent):
            return name
    return "Other"


@dataclass(frozen=True)
class Hit:
    """One report from a browser, already cleaned."""

    event: str  # page_view | engage
    path: str
    visitor: str
    user_id: uuid.UUID | None
    agent: str
    country: str | None
    referrer: str | None  # host
    utm_source: str | None
    utm_campaign: str | None
    seconds: int = 0


async def _current(db: AsyncSession, hit: Hit, now: datetime) -> Visit | None:
    same = Visit.visitor == hit.visitor
    if hit.user_id is not None:
        same = or_(same, Visit.user_id == hit.user_id)
    return await db.scalar(
        select(Visit)
        .where(same, Visit.last_seen_at > now - VISIT_GAP)
        .order_by(Visit.last_seen_at.desc())
        .limit(1)
        .with_for_update()
    )


async def record(db: AsyncSession, hit: Hit, now: datetime) -> None:
    """Add a page view or engaged time to the visitor's current visit (or start one)."""
    visit = await _current(db, hit, now)
    if hit.event == "engage":
        if visit is None or hit.seconds <= 0:
            return
        add = min(hit.seconds, MAX_ENGAGE)
        visit.engaged_seconds += add
        visit.last_seen_at = now
        latest = (
            select(func.max(VisitPage.id))
            .where(VisitPage.visit_id == visit.id, VisitPage.path == hit.path)
            .scalar_subquery()
        )
        await db.execute(
            update(VisitPage).where(VisitPage.id == latest).values(seconds=VisitPage.seconds + add)
        )
        await db.commit()
        return

    if visit is None:
        visit = Visit(
            visitor=hit.visitor,
            user_id=hit.user_id,
            started_at=now,
            last_seen_at=now,
            country=hit.country,
            source=source_of(hit.referrer, hit.utm_source),
            referrer=hit.referrer,
            utm_campaign=(hit.utm_campaign or "")[:60] or None,
            landing=hit.path,
            device=device_of(hit.agent),
            browser=browser_of(hit.agent),
            os=os_of(hit.agent),
            pages=1,
            engaged_seconds=0,
        )
        db.add(visit)
        await db.flush()
    else:
        visit.pages += 1
        visit.last_seen_at = now
        if hit.user_id is not None and visit.user_id is None:
            visit.user_id = hit.user_id  # they signed up or signed in during this visit
        if visit.country is None:
            visit.country = hit.country
    if visit.pages <= MAX_PAGES_KEPT:
        db.add(VisitPage(visit_id=visit.id, path=hit.path, at=now, seconds=0))
    await db.commit()


async def prune(db: AsyncSession, keep_days: int, now: datetime) -> None:
    await db.execute(delete(Visit).where(Visit.started_at < now - timedelta(days=keep_days)))
