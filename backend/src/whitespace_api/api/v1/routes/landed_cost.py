"""Import duties and landed cost for a product in a market. Signed-in only."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status

from whitespace_api.api.deps import AppSettings, DbSession, HttpClient, get_current_user
from whitespace_api.schemas.landed_cost import DutyComparison, LandedCost
from whitespace_api.services import landed_cost as service
from whitespace_api.services import trade as trade_service
from whitespace_shared.gold import COUNTRY_CODE_PATTERN, HS6_PATTERN

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["landed cost"])

CACHE_SECONDS = 300

Market = Annotated[str, Path(pattern=COUNTRY_CODE_PATTERN, description="ISO code, e.g. DEU")]
Exporter = Annotated[str, Query(pattern=COUNTRY_CODE_PATTERN, description="ISO code, e.g. PAK")]
HS6 = Annotated[str, Query(pattern=HS6_PATTERN, description="Six-digit product code")]


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, service.UnavailableError):
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
    return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


SAFE_ERRORS = (trade_service.NotFoundError, service.NotCoveredError, service.UnavailableError)


@router.get("/markets/{market}/duties", response_model=DutyComparison)
async def duties(
    response: Response,
    db: DbSession,
    client: HttpClient,
    settings: AppSettings,
    market: Market,
    exporter: Exporter,
    hs6: HS6,
) -> DutyComparison:
    """Import duty on a product from your country and from the market's main suppliers."""
    try:
        result = await service.duties(
            db, client, exporter=exporter, market=market, hs6=hs6, settings=settings
        )
    except SAFE_ERRORS as exc:
        raise _error(exc) from exc
    response.headers["Cache-Control"] = f"private, max-age={CACHE_SECONDS}"
    return result


@router.get("/markets/{market}/landed-cost", response_model=LandedCost)
async def landed_cost(
    response: Response,
    db: DbSession,
    client: HttpClient,
    settings: AppSettings,
    market: Market,
    exporter: Exporter,
    hs6: HS6,
    cost_usd_kg: Annotated[
        float | None, Query(gt=0, le=10_000, description="Your cost per kg, USD, FOB")
    ] = None,
    freight_pct: Annotated[
        float | None,
        Query(ge=0, le=100, description="Freight and insurance, percent of the FOB value"),
    ] = None,
    freight_usd_kg: Annotated[
        float | None, Query(ge=0, le=1_000, description="Freight and insurance, USD per kg")
    ] = None,
) -> LandedCost:
    """Delivered cost per kg (price + freight + duty): yours against your rivals'."""
    if freight_pct is not None and freight_usd_kg is not None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Give freight as a percentage or per kg, not both",
        )
    try:
        result = await service.landed_cost(
            db, client, exporter=exporter, market=market, hs6=hs6, settings=settings,
            cost_usd_kg=cost_usd_kg,
            freight=service.Freight(pct=freight_pct, usd_kg=freight_usd_kg),
        )  # fmt: skip
    except SAFE_ERRORS as exc:
        raise _error(exc) from exc
    response.headers["Cache-Control"] = f"private, max-age={CACHE_SECONDS}"
    return result
