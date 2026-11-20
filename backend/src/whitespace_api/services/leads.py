"""Company leads: who to contact in a country, found on request and shared by everyone.

Works like market briefs: generated in the background on request (never on page view),
a pending row is the lock, results are reused by every user for `leads_cache_days`,
and each user has a daily limit of new searches. Intro emails are drafted per user.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.agents import llm
from whitespace_api.agents.brief.facts import sector_term
from whitespace_api.agents.leads import LeadsDeps, LeadsError, find_leads, is_past
from whitespace_api.core import tasks
from whitespace_api.core.config import Settings
from whitespace_api.core.http import http_client
from whitespace_api.models.lead import TradeLeads
from whitespace_api.models.user import User
from whitespace_api.repositories import leads as repo
from whitespace_api.repositories import trade as trade_repo
from whitespace_api.schemas.lead import (
    IntroIn,
    IntroOut,
    LeadsContent,
    LeadSide,
    LeadsOut,
    LeadsUsage,
)
from whitespace_api.services import outreach, pipeline
from whitespace_shared.naming import everyday_name

log = logging.getLogger(__name__)

ABANDONED_AFTER = timedelta(minutes=3)


class NotFoundError(Exception):
    """Unknown product or country. The message is safe to show."""


class LimitError(Exception):
    """The user reached today's limit. The message is safe to show."""


def _out(row: TradeLeads | None, side: LeadSide, settings: Settings) -> LeadsOut:
    if row is None:
        return LeadsOut(status="missing", side=side)
    stale = row.updated_at < datetime.now(UTC) - timedelta(days=settings.leads_cache_days)
    content = LeadsContent.model_validate(row.content) if row.content else None
    if content is not None:
        # Fairs found weeks ago may have taken place since.
        today = date.today()
        content.events = [
            e for e in content.events if not is_past(e.name, e.when, today.year, today.month)
        ]
    return LeadsOut(
        status=row.status,
        side=side,
        content=content,
        error=row.error,
        generated_at=row.updated_at if row.status == "ready" else None,
        stale=stale and row.status == "ready",
        usage=LeadsUsage.model_validate(row.usage) if row.usage else None,
    )


async def _names(db: AsyncSession, hs6: str, country: str) -> tuple[str, str]:
    """(everyday product name, country name), or NotFoundError."""
    name, place, _ = await _lookup(db, hs6, country)
    return name, place


async def _lookup(db: AsyncSession, hs6: str, country: str) -> tuple[str, str, str]:
    """(everyday product name, country name, official product description)."""
    product = await trade_repo.get_product(db, hs6)
    place = await trade_repo.get_country(db, country)
    if product is None:
        raise NotFoundError(f"Unknown product {hs6}")
    if place is None:
        raise NotFoundError(f"Unknown country {country}")
    return everyday_name(hs6, product.description), place.name, product.description


async def get_leads(
    db: AsyncSession, *, hs6: str, country: str, side: LeadSide, settings: Settings
) -> LeadsOut:
    return _out(await repo.get(db, hs6, country, side), side, settings)


async def request_leads(
    db: AsyncSession,
    user: User,
    *,
    hs6: str,
    country: str,
    side: LeadSide,
    settings: Settings,
) -> LeadsOut:
    """Start a search, unless fresh leads exist or a search is already running."""
    await _names(db, hs6, country)  # 404s
    current = _out(await repo.get(db, hs6, country, side), side, settings)
    if current.status == "ready" and not current.stale:
        return current  # cached: no credits or tokens spent
    since = datetime.now(UTC) - timedelta(days=1)
    if await repo.requests_since(db, user.id, since) >= settings.leads_daily_limit:
        raise LimitError(
            f"You've reached today's limit of {settings.leads_daily_limit} new company "
            "searches. Lists already found stay available."
        )
    claimed = await repo.claim(
        db, hs6=hs6, country=country, side=side, user_id=user.id, abandoned_after=ABANDONED_AFTER
    )
    if claimed:
        tasks.spawn(_generate(hs6=hs6, country=country, side=side, settings=settings))
    return _out(await repo.get(db, hs6, country, side), side, settings)


async def _generate(*, hs6: str, country: str, side: LeadSide, settings: Settings) -> None:
    where = {"hs6": hs6, "country": country, "side": side}
    async with tasks.session_factory() as db:

        async def finish(status: str, **result: Any) -> None:
            await repo.finish(db, hs6=hs6, country=country, side=side, status=status, **result)

        try:
            product, place, description = await _lookup(db, hs6, country)
            key = settings.tavily_api_key
            if key is None:
                await finish("failed", error="Company search isn't set up on this server yet.")
                return
            deps = LeadsDeps(
                http=http_client(),
                search_key=key.get_secret_value(),
                chat=lambda spec: llm.get_chat_model(spec, settings=settings),
            )
            run = await find_leads(
                deps,
                product=product,
                country=place,
                side=side,
                year=date.today().year,
                month=date.today().month,
                sector=sector_term(hs6, product),
                detail=description,
            )
            usage = LeadsUsage(
                searches=run.searches,
                pages_read=run.pages_read,
                input_tokens=sum(c["input_tokens"] for c in run.calls),
                output_tokens=sum(c["output_tokens"] for c in run.calls),
                models=sorted({c["model"] for c in run.calls}),
            ).model_dump()
            log.info(
                "Leads %s ready: %d companies, %d events, %d removed, %s",
                where,
                len(run.content.companies),
                len(run.content.events),
                run.content.removed,
                usage,
            )
            await finish("ready", content=run.content.model_dump(), usage=usage)
        except LeadsError as exc:
            await finish("failed", error=str(exc))
        except Exception:
            log.exception("Leads %s failed", where)
            await finish("failed", error="The company search couldn't run right now. Try again.")


# --- intro emails -------------------------------------------------------------------


async def draft_intro(db: AsyncSession, user: User, body: IntroIn, settings: Settings) -> IntroOut:
    """A first email to a company on a lead list (same writer and checks as the pipeline)."""
    product, place = await _names(db, body.hs6, body.country)
    me = await outreach.sender(db, user)
    try:
        await outreach.spend(db, user, settings)
    except pipeline.LimitError as exc:
        raise LimitError(str(exc)) from exc
    role = "importer" if body.side == "suppliers" else "supplier"
    facts = [
        f"Product: {product} (HS {body.hs6})",
        f"Recipient: {body.company} ({body.kind}), {place}"
        + (f"; deals in {body.handles}" if body.handles else ""),
        f"The sender is a {role} writing to them about this product",
        *me.lines,
    ]
    fallback = outreach.template(
        purpose="first",
        company=body.company,
        product=product,
        place=place,
        home=me.home,
        side=body.side,
        signature=me.signature,
    )
    written = await outreach.write_email(
        settings,
        purpose="first",
        language=body.language,
        facts=facts,
        signature=me.signature,
        thread=[],
        notes=None,
        fallback=fallback,
    )
    return IntroOut(
        subject=written.subject,
        body=written.body,
        drafted_by=written.drafted_by,
        checks=outreach.draft_checks(f"{written.subject}\n{written.body}", [*facts, me.signature]),
    )
