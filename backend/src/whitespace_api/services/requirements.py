"""Import requirements for a lane (product, market, exporter): researched once in the
background and shared; each user keeps their own checklist ticks."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.agents import llm
from whitespace_api.agents.brief.facts import sector_term
from whitespace_api.agents.requirements import (
    RequirementsDeps,
    RequirementsError,
    find_requirements,
)
from whitespace_api.core import tasks
from whitespace_api.core.config import Settings
from whitespace_api.core.http import http_client
from whitespace_api.models.requirements import MarketRequirements
from whitespace_api.models.user import User
from whitespace_api.repositories import requirements as repo
from whitespace_api.repositories import trade as trade_repo
from whitespace_api.schemas.requirements import (
    RequirementsContent,
    RequirementsOut,
    RequirementsUsage,
)
from whitespace_api.services import landed_cost
from whitespace_shared.naming import everyday_name

log = logging.getLogger(__name__)
ABANDONED_AFTER = timedelta(minutes=4)  # a run that hasn't finished by then has died


class NotFoundError(Exception):
    pass


class LimitError(Exception):
    pass


def _out(row: MarketRequirements | None, settings: Settings, done: list[str]) -> RequirementsOut:
    if row is None:
        return RequirementsOut(status="missing")
    content = RequirementsContent.model_validate(row.content) if row.content else None
    age = datetime.now(UTC) - row.updated_at
    keys = {i.key for i in content.items} if content else set()
    return RequirementsOut(
        status=row.status,
        content=content,
        error=row.error,
        generated_at=row.updated_at if content is not None else None,
        stale=row.status == "ready" and age > timedelta(days=settings.requirements_cache_days),
        done=[k for k in done if k in keys],
    )


async def _names(
    db: AsyncSession, hs6: str, market: str, exporter: str
) -> tuple[str, str, str, str]:
    """(everyday product name, official description, market name, exporter name)."""
    product = await trade_repo.get_product(db, hs6)
    if product is None:
        raise NotFoundError(f"Unknown product {hs6}")
    countries = await trade_repo.countries_by_code(db, [market, exporter])
    for code in (market, exporter):
        if code not in countries:
            raise NotFoundError(f"Unknown country {code}")
    if market == exporter:
        raise NotFoundError("The market and the exporter are the same country")
    return (
        everyday_name(hs6, product.description),
        product.description,
        countries[market].name,
        countries[exporter].name,
    )


async def _scheme(
    db: AsyncSession, *, hs6: str, market: str, exporter: str, settings: Settings
) -> str | None:
    """The trade preference this lane uses ("EU GSP+"), from the duty data; None if the
    standard rate applies or the duty data can't be reached."""
    try:
        comparison = await landed_cost.duties(
            db, http_client(), exporter=exporter, market=market, hs6=hs6, settings=settings
        )
    except Exception as exc:  # research goes on without it
        log.info("No duty data for requirements %s: %s", (hs6, market, exporter), exc)
        return None
    return comparison.yours.scheme if comparison.yours.kind == "preference" else None


async def get_requirements(
    db: AsyncSession, user: User, *, hs6: str, market: str, exporter: str, settings: Settings
) -> RequirementsOut:
    row = await repo.get(db, (hs6, market, exporter))
    return _out(row, settings, await repo.done(db, user.id, hs6, market))


async def request_requirements(
    db: AsyncSession, user: User, *, hs6: str, market: str, exporter: str, settings: Settings
) -> RequirementsOut:
    """Start the research unless a fresh result exists or a run is already going."""
    await _names(db, hs6, market, exporter)  # 404s
    key = (hs6, market, exporter)
    current = await get_requirements(
        db, user, hs6=hs6, market=market, exporter=exporter, settings=settings
    )
    if current.status == "ready" and not current.stale:
        return current
    since = datetime.now(UTC) - timedelta(days=1)
    if await repo.requests_since(db, user.id, since) >= settings.requirements_daily_limit:
        raise LimitError(
            f"You've reached today's limit of {settings.requirements_daily_limit} new "
            "requirement checks. Checks already done stay available."
        )
    run_id = await repo.claim(db, key, user_id=user.id, abandoned_after=ABANDONED_AFTER)
    if run_id is not None:
        tasks.spawn(_research(key, run_id, settings))
    return await get_requirements(
        db, user, hs6=hs6, market=market, exporter=exporter, settings=settings
    )


async def _research(key: repo.Key, run_id: uuid.UUID, settings: Settings) -> None:
    hs6, market, exporter = key
    async with tasks.session_factory() as db:

        async def fail(message: str) -> None:
            await repo.finish(db, key, run_id, status="failed", error=message, keep_content=True)

        try:
            product, detail, market_name, exporter_name = await _names(db, hs6, market, exporter)
            if settings.tavily_api_key is None:
                await fail("Requirement research isn't set up on this server yet.")
                return
            scheme = await _scheme(db, hs6=hs6, market=market, exporter=exporter, settings=settings)
            deps = RequirementsDeps(
                http=http_client(),
                search_key=settings.tavily_api_key.get_secret_value(),
                chat=lambda spec: llm.get_chat_model(spec, settings=settings),
            )
            run = await find_requirements(
                deps,
                product=product,
                detail=detail,
                market=market_name,
                market_code=market,
                exporter=exporter_name,
                sector=sector_term(hs6, product),
                scheme=scheme,
            )
            usage = RequirementsUsage(
                searches=run.searches,
                pages_read=run.pages_read,
                input_tokens=sum(c["input_tokens"] for c in run.calls),
                output_tokens=sum(c["output_tokens"] for c in run.calls),
                models=sorted({c["model"] for c in run.calls}),
            ).model_dump()
            stored = await repo.finish(
                db, key, run_id, status="ready", content=run.content.model_dump(), usage=usage
            )
            log.info(
                "Requirements %s %s: %d items, %d removed, %s",
                key,
                "ready" if stored else "superseded",
                len(run.content.items),
                run.content.removed,
                usage,
            )
        except (RequirementsError, NotFoundError) as exc:
            await fail(str(exc))
        except Exception:
            log.exception("Requirements %s failed", key)
            await fail("The requirements couldn't be researched right now. Please try again.")


async def set_done(
    db: AsyncSession, user: User, *, hs6: str, market: str, item: str, value: bool
) -> None:
    await repo.set_done(db, user.id, hs6, market, item, value)
