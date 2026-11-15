"""Buying: where to source a product."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from whitespace_api.api.deps import DbSession, get_current_user
from whitespace_api.schemas.sourcing import SourceProductMatch, SourcingPage
from whitespace_api.services import sourcing as sourcing_service
from whitespace_shared.gold import COUNTRY_CODE_PATTERN, HS6_PATTERN

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["sourcing"])

CACHE_SECONDS = 300


@router.get("/sourcing", response_model=SourcingPage)
async def sourcing(
    response: Response,
    db: DbSession,
    buyer: Annotated[str, Query(pattern=COUNTRY_CODE_PATTERN, description="Buying country")],
    hs6: Annotated[str, Query(pattern=HS6_PATTERN)],
) -> SourcingPage:
    """The best countries to buy a product from, with prices, growth and reliability."""
    try:
        page = await sourcing_service.sourcing(db, buyer=buyer, hs6=hs6)
    except sourcing_service.SourcingNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    response.headers["Cache-Control"] = f"private, max-age={CACHE_SECONDS}"
    return page


@router.get("/sourcing/products/search", response_model=list[SourceProductMatch])
async def search_products(
    db: DbSession,
    q: Annotated[str, Query(min_length=2, max_length=100)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[SourceProductMatch]:
    """Products to buy, by everyday words or an HS code."""
    return await sourcing_service.search_products(db, q=q, limit=limit)
