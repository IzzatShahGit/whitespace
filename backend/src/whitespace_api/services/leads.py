"""Company leads: who to contact in a country, found on request and shared by everyone.

Works like market briefs: generated in the background on request (never on page view),
a pending row is the lock, results are reused by every user for `leads_cache_days`,
and each user has a daily limit of new searches. Intro emails are drafted per user.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.agents import llm
from whitespace_api.agents.brief.facts import sector_term
from whitespace_api.agents.leads import LeadsDeps, LeadsError, find_leads
from whitespace_api.core import tasks
from whitespace_api.core.config import Settings
from whitespace_api.core.http import http_client
from whitespace_api.models.lead import TradeLeads
from whitespace_api.models.user import User
from whitespace_api.repositories import leads as repo
from whitespace_api.repositories import profiles as profile_repo
from whitespace_api.repositories import trade as trade_repo
from whitespace_api.repositories import usage as usage_repo
from whitespace_api.schemas.lead import (
    IntroIn,
    IntroOut,
    LeadsContent,
    LeadSide,
    LeadsOut,
    LeadsUsage,
)
from whitespace_shared.naming import everyday_name

log = logging.getLogger(__name__)

ABANDONED_AFTER = timedelta(minutes=3)
INTRO_KIND = "intro"


class NotFoundError(Exception):
    """Unknown product or country. The message is safe to show."""


class LimitError(Exception):
    """The user reached today's limit. The message is safe to show."""


def _out(row: TradeLeads | None, side: LeadSide, settings: Settings) -> LeadsOut:
    if row is None:
        return LeadsOut(status="missing", side=side)
    stale = row.updated_at < datetime.now(UTC) - timedelta(days=settings.leads_cache_days)
    return LeadsOut(
        status=row.status,
        side=side,
        content=LeadsContent.model_validate(row.content) if row.content else None,
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


class IntroDraft(BaseModel):
    subject: str = Field(description="At most 10 words")
    body: str = Field(description="Under 150 words, plain text, with [placeholders]")


INTRO_SPEC = llm.CallSpec(tier="small", max_output_tokens=500, schema=IntroDraft)

INTRO_SYSTEM = """You write short, polite first-contact business emails for small \
traders. Plain text, under 150 words, no hype, no invented facts about either company. \
Use placeholders in square brackets for anything you don't know: [Your name], \
[Your company], [Website], [Phone]. Propose one concrete next step (a catalogue, price \
list or samples). Never claim certifications, volumes or prices. Format: greeting line, \
two short paragraphs, sign-off, separated by blank lines."""


def _intro_template(
    *, side: LeadSide, company: str, product: str, place: str, home: str | None
) -> IntroOut:
    origin = f" based in {home}" if home else ""
    if side == "buyers":
        subject = f"{product.capitalize()} supplier for {company}"
        ask = (
            f"We're a {product} supplier{origin} and are looking for importers and "
            f"distributors in {place}. I'd be glad to send our catalogue and price list, "
            "and samples if useful."
        )
    else:
        subject = f"Sourcing enquiry: {product}"
        ask = (
            f"We're a buyer{origin} looking for reliable {product} manufacturers in "
            f"{place}. Could you share your catalogue, minimum order quantity and prices?"
        )
    body = (
        f"Dear {company} team,\n\n{ask}\n\nWould you be open to a short call next week?"
        "\n\nKind regards,\n[Your name]\n[Your company]\n[Website] · [Phone]"
    )
    return IntroOut(subject=subject, body=body, drafted_by="template")


async def draft_intro(db: AsyncSession, user: User, body: IntroIn, settings: Settings) -> IntroOut:
    product, place = await _names(db, body.hs6, body.country)
    profile = await profile_repo.get_profile(db, user.id)
    home_country = (
        await trade_repo.get_country(db, profile.exporter) if profile is not None else None
    )
    home = home_country.name if home_country else None
    count = await usage_repo.consume(
        db, user_id=user.id, kind=INTRO_KIND, day=date.today(), limit=settings.intro_daily_limit
    )
    if count is None:
        raise LimitError(f"You've reached today's limit of {settings.intro_daily_limit} drafts.")
    await db.commit()
    fallback = _intro_template(
        side=body.side, company=body.company, product=product, place=place, home=home
    )
    role = "a supplier selling to" if body.side == "buyers" else "a buyer sourcing from"
    ask = (
        f"Write a first email from {role} this company.\n"
        f"Sender: a small business{f' in {home}' if home else ''}.\n"
        f"Recipient: {body.company} ({body.kind}) in {place}"
        f"{f', which deals in {body.handles}' if body.handles else ''}.\n"
        f"Product: {product}."
    )
    try:
        out = await llm.get_chat_model(INTRO_SPEC, settings=settings).ainvoke(
            [("system", INTRO_SYSTEM), ("human", ask)]
        )
    except Exception as exc:
        log.warning("Intro draft fell back to the template: %s", type(exc).__name__)
        return fallback
    draft: IntroDraft | None = out.get("parsed")
    if draft is None or not draft.body.strip():
        return fallback
    return IntroOut(subject=draft.subject.strip(), body=draft.body.strip(), drafted_by="ai")
