"""Signed-out endpoints for the landing page: rate-limited, read-only, cacheable."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from whitespace_api.api.deps import DbSession
from whitespace_api.core.ratelimit import RateLimiter, limit
from whitespace_api.schemas.public import Preview, PreviewMarket
from whitespace_api.services import trade as trade_service
from whitespace_shared.gold import COUNTRY_CODE_PATTERN

router = APIRouter(prefix="/public", tags=["public"])

PREVIEW_MARKETS = 3
CACHE_SECONDS = 3600
_preview_limit = RateLimiter(per_minute=20)


@router.get("/preview", response_model=Preview)
async def preview(
    request: Request,
    response: Response,
    db: DbSession,
    exporter: Annotated[str, Query(pattern=COUNTRY_CODE_PATTERN)],
    q: Annotated[str, Query(min_length=2, max_length=60)],
) -> Preview:
    """Top markets for a product typed in plain words, e.g. "towels" from PAK."""
    limit(_preview_limit, request)
    try:
        found = await trade_service.search_products(db, exporter=exporter, q=q, limit=1)
    except trade_service.NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No product matches “{q}”")
    page = await trade_service.ranked_markets(
        db, exporter=exporter, hs6=found[0].hs6, limit=PREVIEW_MARKETS, offset=0
    )
    response.headers["Cache-Control"] = f"public, max-age={CACHE_SECONDS}"
    return Preview(
        exporter=page.exporter,
        product=page.product,
        total=page.total,
        data_year=page.data.end_year if page.data else None,
        markets=[
            PreviewMarket(
                market=m.market,
                action=m.verdict.action,
                headline=m.verdict.headline,
                tone=m.verdict.tone,
                imports_usd=m.market_imports_usd,
                growth=m.import_growth_3y,
            )
            for m in page.items
        ],
    )
