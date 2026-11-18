"""The weekly email: one user's follow-ups, pipeline, market moves, checklists and fairs.

Built only from that user's own data and the shared research; nothing is generated.
Sent only to verified addresses that opted in, with an unsubscribe link (and header).
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.agents.leads import is_past
from whitespace_api.core.config import Settings
from whitespace_api.models.lead import TradeLeads
from whitespace_api.models.pipeline import PipelineContact
from whitespace_api.models.profile import UserProfile
from whitespace_api.models.requirements import MarketRequirements, RequirementCheck
from whitespace_api.models.user import User
from whitespace_api.models.watch import Notification, Watch
from whitespace_api.notify.email import EmailMessage
from whitespace_api.repositories import trade as trade_repo
from whitespace_api.schemas.pipeline import ACTIVE
from whitespace_api.services.pipeline import STAGE_WORDS
from whitespace_shared.naming import everyday_name

MAX_LINES = 5
MAX_LANES = 6


def unsubscribe_token(user_id: uuid.UUID, settings: Settings) -> str:
    secret = settings.jwt_secret.get_secret_value().encode()
    return hmac.new(secret, f"unsubscribe:{user_id}".encode(), hashlib.sha256).hexdigest()[:32]


def valid_unsubscribe(user_id: uuid.UUID, token: str, settings: Settings) -> bool:
    return hmac.compare_digest(unsubscribe_token(user_id, settings), token)


def unsubscribe_link(user_id: uuid.UUID, settings: Settings) -> str:
    base = settings.public_app_url.rstrip("/")
    return f"{base}/unsubscribe?u={user_id}&t={unsubscribe_token(user_id, settings)}"


@dataclass
class Digest:
    subject: str
    text: str


def _section(title: str, lines: list[str]) -> str:
    return f"{title.upper()}\n" + "\n".join(lines)


async def build(db: AsyncSession, user: User, settings: Settings, today: date) -> Digest | None:
    """The user's digest, or None when there's nothing worth an email this week."""
    app = settings.public_app_url.rstrip("/")
    week_ago = datetime.now(UTC) - timedelta(days=7)
    sections: list[str] = []
    headline: list[str] = []

    contacts = list(
        await db.scalars(select(PipelineContact).where(PipelineContact.user_id == user.id))
    )
    markets = await trade_repo.countries_by_code(db, sorted({c.market for c in contacts}))

    def where(code: str) -> str:
        return markets[code].name if code in markets else code

    due = sorted(
        (c for c in contacts if c.stage in ACTIVE and c.follow_up_on and c.follow_up_on <= today),
        key=lambda c: (c.follow_up_on, c.name),
    )
    if due:
        headline.append(f"{len(due)} follow-up{'s' if len(due) > 1 else ''} due")
        lines = [
            f"- {c.name} ({where(c.market)}): {STAGE_WORDS[c.stage].lower()}, "
            f"due {c.follow_up_on:%d %b}"
            for c in due[:MAX_LINES]
        ]
        if len(due) > MAX_LINES:
            lines.append(f"- and {len(due) - MAX_LINES} more")
        lines.append(f"Open your pipeline: {app}/app/pipeline")
        sections.append(_section("Follow-ups due", lines))

    active = [c for c in contacts if c.stage in ACTIVE]
    if active:
        counts = {s: sum(1 for c in contacts if c.stage == s) for s in STAGE_WORDS}
        line = " · ".join(f"{STAGE_WORDS[s]} {n}" for s, n in counts.items() if n)
        sections.append(_section("Your pipeline", [line]))

    moves = list(
        await db.scalars(
            select(Notification)
            .where(
                Notification.user_id == user.id,
                Notification.created_at >= week_ago,
                Notification.kind != "follow_up",
            )
            .order_by(Notification.created_at.desc())
            .limit(MAX_LINES)
        )
    )
    if moves:
        headline.append(f"{len(moves)} market update{'s' if len(moves) > 1 else ''}")
        sections.append(
            _section(
                "This week in your markets",
                [f"- {n.title}" for n in moves] + [f"See them all: {app}/app/watchlist"],
            )
        )

    # Lanes the user is working on: pipeline first, then watched markets.
    lanes: list[tuple[str, str]] = []
    for c in sorted(active, key=lambda c: c.updated_at, reverse=True):
        if (c.hs6, c.market) not in lanes:
            lanes.append((c.hs6, c.market))
    watched = await db.execute(
        select(Watch.hs6, Watch.market).where(Watch.user_id == user.id).order_by(Watch.created_at)
    )
    for hs6, market in watched.all():
        if (hs6, market) not in lanes:
            lanes.append((hs6, market))
    lanes = lanes[:MAX_LANES]

    exporter = await db.scalar(select(UserProfile.exporter).where(UserProfile.user_id == user.id))
    if lanes:
        products = await trade_repo.products_by_code(db, sorted({h for h, _ in lanes}))
        places = await trade_repo.countries_by_code(db, sorted({m for _, m in lanes}))

        def lane_name(hs6: str, market: str) -> str:
            product = products.get(hs6)
            name = everyday_name(hs6, product.description) if product else hs6
            return f"{name.capitalize()} to {places[market].name if market in places else market}"

        checklist: list[str] = []
        if exporter:
            for hs6, market in lanes:
                row = await db.get(MarketRequirements, (hs6, market, exporter))
                items = (row.content or {}).get("items", []) if row and row.content else []
                if not items:
                    continue
                keys = {i["key"] for i in items}
                ticked = await db.scalar(
                    select(func.count()).where(
                        RequirementCheck.user_id == user.id,
                        RequirementCheck.hs6 == hs6,
                        RequirementCheck.market == market,
                        RequirementCheck.item.in_(keys),
                    )
                )
                if (ticked or 0) < len(items):
                    checklist.append(f"- {lane_name(hs6, market)}: {ticked} of {len(items)} done")
        if checklist:
            sections.append(_section("Before you ship", checklist))

        fairs: list[str] = []
        seen: set[str] = set()
        for hs6, market in lanes:
            found = await db.get(TradeLeads, (hs6, market, "buyers"))
            events = (found.content or {}).get("events", []) if found and found.content else []
            for event in events:
                name, when = event.get("name", ""), event.get("when")
                upcoming = when and any(str(y) in when for y in (today.year, today.year + 1))
                if not upcoming or is_past(name, when, today.year, today.month):
                    continue
                if name.lower() in seen:
                    continue
                seen.add(name.lower())
                city = event.get("city")
                fairs.append(f"- {name}{f', {city}' if city else ''}: {when}")
        if fairs:
            sections.append(_section("Trade fairs coming up", fairs[:MAX_LINES]))

    if not due and not moves and len(sections) < 2:
        return None  # nothing new or actionable: no email this week
    first = user.full_name.split()[0] if user.full_name.strip() else "there"
    subject = "Your Whitespace week" + (f": {', '.join(headline)}" if headline else "")
    text = (
        f"Hi {first},\n\nHere's your week.\n\n"
        + "\n\n".join(sections)
        + "\n\n--\nYou're getting this because you turned on the weekly email in Whitespace."
        f"\nStop these emails: {unsubscribe_link(user.id, settings)}\n"
    )
    return Digest(subject=subject, text=text)


def message(user: User, digest: Digest, settings: Settings) -> EmailMessage:
    return EmailMessage(
        to=user.email,
        subject=digest.subject,
        text=digest.text,
        headers={"List-Unsubscribe": f"<{unsubscribe_link(user.id, settings)}>"},
    )
