"""Market search endpoints. All require sign-in.

Responses are cacheable briefly in the user's own browser (private: they sit behind
authentication and carry per-user flags such as "already selling here").
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status

from whitespace_api.api.deps import AppSettings, CurrentUser, DbSession, get_current_user
from whitespace_api.schemas.trade import (
    CountryOut,
    MarketDetail,
    MarketsPage,
    NicheDetail,
    ProductMatch,
    RecentMovement,
    SectorOut,
)
from whitespace_api.services import profile as profile_service
from whitespace_api.services import recent as recent_service
from whitespace_api.services import trade as trade_service
from whitespace_shared.gold import COUNTRY_CODE_PATTERN, HS6_PATTERN

CACHE_SECONDS = 300


def _cacheable(response: Response) -> None:
    response.headers["Cache-Control"] = f"private, max-age={CACHE_SECONDS}"


router = APIRouter(dependencies=[Depends(get_current_user), Depends(_cacheable)])

Exporter = Annotated[str, Query(pattern=COUNTRY_CODE_PATTERN, description="ISO code, e.g. PAK")]
HS6 = Annotated[str, Query(pattern=HS6_PATTERN, description="Six-digit product code")]
Limit = Annotated[int, Query(ge=1, le=100)]


def _not_found(exc: trade_service.NotFoundError) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


@router.get("/countries/exporters", response_model=list[CountryOut], tags=["markets"])
async def exporters(db: DbSession) -> list[CountryOut]:
    """Exporter countries we have ranked markets for."""
    return await trade_service.list_exporters(db)


@router.get("/countries", response_model=list[CountryOut], tags=["markets"])
async def countries(db: DbSession) -> list[CountryOut]:
    """Every country in the trade data (e.g. for "where do you already sell?")."""
    return await trade_service.list_countries(db)


@router.get("/products/search", response_model=list[ProductMatch], tags=["markets"])
async def search_products(
    db: DbSession,
    exporter: Exporter,
    q: Annotated[str, Query(min_length=2, max_length=100, description="Words or an HS code")],
    limit: Limit = 10,
) -> list[ProductMatch]:
    """Products matching everyday words, limited to ones with markets for this exporter."""
    try:
        return await trade_service.search_products(db, q=q, exporter=exporter, limit=limit)
    except trade_service.NotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/markets", response_model=MarketsPage, tags=["markets"])
async def ranked_markets(
    db: DbSession,
    user: CurrentUser,
    exporter: Exporter,
    hs6: HS6,
    limit: Limit = 20,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> MarketsPage:
    """Markets ranked by opportunity, each with a label and three reasons."""
    try:
        return await trade_service.ranked_markets(
            db,
            exporter=exporter,
            hs6=hs6,
            limit=limit,
            offset=offset,
            selling_in=await profile_service.selling_in(db, user, exporter),
        )
    except trade_service.NotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/markets/{market}/recent", response_model=RecentMovement, tags=["markets"])
async def recent_movement(
    db: DbSession,
    settings: AppSettings,
    market: Annotated[str, Path(pattern=COUNTRY_CODE_PATTERN)],
    exporter: Exporter,
    hs6: HS6,
) -> RecentMovement:
    """Monthly imports since the annual data ends (EU members and the US only)."""
    try:
        return await recent_service.recent_movement(
            db, market=market, hs6=hs6, exporter=exporter, settings=settings
        )
    except recent_service.NotCoveredError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except recent_service.UnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


@router.get("/markets/{market}", response_model=MarketDetail, tags=["markets"])
async def market_detail(
    db: DbSession,
    user: CurrentUser,
    market: Annotated[str, Path(pattern=COUNTRY_CODE_PATTERN)],
    exporter: Exporter,
    hs6: HS6,
) -> MarketDetail:
    """One market in depth: the scores, the reasons, and who supplies it."""
    try:
        return await trade_service.market_detail(
            db,
            exporter=exporter,
            hs6=hs6,
            market=market,
            selling_in=await profile_service.selling_in(db, user, exporter),
        )
    except trade_service.NotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/niches", response_model=list[SectorOut], tags=["markets"])
async def niches(db: DbSession, exporter: Exporter) -> list[SectorOut]:
    """Plain-language product groups (e.g. "Socks & hosiery"), by sector."""
    try:
        return await trade_service.list_niches(db, exporter=exporter)
    except trade_service.NotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/niches/{slug}", response_model=NicheDetail, tags=["markets"])
async def niche_detail(
    db: DbSession,
    user: CurrentUser,
    slug: Annotated[str, Path(pattern=r"^[a-z0-9-]{1,40}$")],
    exporter: Exporter,
) -> NicheDetail:
    """A niche's products for this exporter, each with its best market."""
    try:
        return await trade_service.niche_detail(
            db,
            slug=slug,
            exporter=exporter,
            selling_in=await profile_service.selling_in(db, user, exporter),
        )
    except trade_service.NotFoundError as exc:
        raise _not_found(exc) from exc
