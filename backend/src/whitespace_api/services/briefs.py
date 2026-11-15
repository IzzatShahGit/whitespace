"""AI market briefs: generated on request, in the background, then shared and cached.

- A brief is only generated when a user asks for it (never on page view), and is then
  reused by everyone who opens that market for `brief_cache_days`.
- Generation runs as a background task; the client polls. A pending row acts as a lock,
  so one market is never generated twice at once.
- Each user can request a limited number of new briefs per day.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.agents import llm
from whitespace_api.agents.brief import facts as brief_facts
from whitespace_api.agents.brief.graph import BriefDeps, BriefError, build_graph
from whitespace_api.agents.brief.research import plan_queries
from whitespace_api.core import tasks
from whitespace_api.core.config import Settings
from whitespace_api.core.http import http_client
from whitespace_api.integrations.monthly_trade import EU_MEMBERS, EXPORTER_CODES
from whitespace_api.models.brief import MarketBrief
from whitespace_api.models.user import User
from whitespace_api.repositories import briefs as repo
from whitespace_api.repositories import monthly as monthly_repo
from whitespace_api.schemas.brief import BriefContent, BriefOut, BriefUsage
from whitespace_api.schemas.trade import MarketDetail, RecentMovement
from whitespace_api.services import recent as recent_service
from whitespace_api.services import trade as trade_service
from whitespace_shared.naming import everyday_name, short_product

log = logging.getLogger(__name__)

# A job that hasn't finished in this time is treated as abandoned (e.g. a restart).
ABANDONED_AFTER = timedelta(minutes=3)


# Injectable for tests: where background jobs get their own database session.
class LimitError(Exception):
    """The user reached today's brief limit. The message is safe to show."""


def _out(row: MarketBrief | None, settings: Settings) -> BriefOut:
    if row is None:
        return BriefOut(status="missing")
    stale = row.updated_at < datetime.now(UTC) - timedelta(days=settings.brief_cache_days)
    return BriefOut(
        status=row.status,
        content=BriefContent.model_validate(row.content) if row.content else None,
        error=row.error,
        generated_at=row.updated_at if row.status == "ready" else None,
        stale=stale and row.status == "ready",
        usage=BriefUsage.model_validate(row.usage) if row.usage else None,
    )


async def get_brief(
    db: AsyncSession, *, exporter: str, hs6: str, market: str, settings: Settings
) -> BriefOut:
    return _out(await repo.get(db, exporter, hs6, market), settings)


async def request_brief(
    db: AsyncSession, user: User, *, exporter: str, hs6: str, market: str, settings: Settings
) -> BriefOut:
    """Start generating, unless a fresh brief exists or one is already being written."""
    await trade_service.market_detail(db, exporter=exporter, hs6=hs6, market=market)  # 404s
    current = _out(await repo.get(db, exporter, hs6, market), settings)
    if current.status == "ready" and not current.stale:
        return current  # cached: no tokens spent
    since = datetime.now(UTC) - timedelta(days=1)
    if await repo.requests_since(db, user.id, since) >= settings.brief_daily_limit:
        raise LimitError(
            f"You've reached today's limit of {settings.brief_daily_limit} new briefs. "
            "Existing briefs stay available."
        )
    claimed = await repo.claim(
        db,
        exporter=exporter,
        hs6=hs6,
        market=market,
        user_id=user.id,
        abandoned_after=ABANDONED_AFTER,
    )
    if claimed:
        tasks.spawn(_generate(exporter=exporter, hs6=hs6, market=market, settings=settings))
    return _out(await repo.get(db, exporter, hs6, market), settings)


async def _recent(db: AsyncSession, market: str, hs6: str, exporter: str) -> RecentMovement | None:
    """Monthly data if it's already cached; never fetched just for a brief."""
    cached = await monthly_repo.get_cached(db, market, hs6)
    if cached is None:
        return None
    try:
        return recent_service.summarise(
            cached.payload,
            exporter_code=EXPORTER_CODES.get(exporter, {}).get(cached.source),
            fetched_at=cached.fetched_at,
            stale=False,
        )
    except recent_service.UnavailableError:
        return None


def _context(detail: MarketDetail) -> str:
    product = short_product(detail.product.description)
    return (
        f"Exporter country: {detail.exporter.name}. Product: {product} "
        f"(HS {detail.product.hs6}). Target market: {detail.market.market.name}."
    )


def _usage(calls: list[dict[str, Any]]) -> dict[str, Any]:
    return BriefUsage(
        calls=len(calls),
        input_tokens=sum(c["input_tokens"] for c in calls),
        output_tokens=sum(c["output_tokens"] for c in calls),
        models=sorted({c["model"] for c in calls}),
    ).model_dump()


async def _generate(*, exporter: str, hs6: str, market: str, settings: Settings) -> None:
    where = {"exporter": exporter, "hs6": hs6, "market": market}
    async with tasks.session_factory() as db:

        async def finish(status: str, **result: Any) -> None:
            await repo.finish(
                db, exporter=exporter, hs6=hs6, market=market, status=status, **result
            )

        try:
            detail = await trade_service.market_detail(
                db, exporter=exporter, hs6=hs6, market=market
            )
            facts = brief_facts.build_facts(detail, await _recent(db, market, hs6, exporter))
            search_key = settings.tavily_api_key
            deps = BriefDeps(
                http=http_client(),
                search_key=search_key.get_secret_value() if search_key else None,
                chat=lambda spec: llm.get_chat_model(spec, settings=settings),
            )
            name = everyday_name(hs6, detail.product.description)
            queries = plan_queries(
                name,
                brief_facts.sector_term(hs6, name),
                detail.market.market.name,
                detail.exporter.name,
                date.today(),
                bloc="European Union" if market in EU_MEMBERS else None,
            )
            state = await build_graph(deps).ainvoke(
                {"context": _context(detail), "facts": facts, "queries": queries, "usage": []}
            )
            usage = _usage(state.get("usage", []))
            log.info("Brief %s ready: %s", where, usage)
            await finish("ready", content=state["content"].model_dump(), usage=usage)
        except BriefError as exc:
            await finish("failed", error=str(exc))
        except Exception:
            log.exception("Brief %s failed", where)
            await finish("failed", error="The brief couldn't be generated right now. Try again.")
