"""Amazon FBA unit economics: signed in, and a rate-limited signed-out version for the
free calculator page. Both compute per request and store nothing."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from whitespace_api.api.deps import AppSettings, DbSession, HttpClient, get_current_user
from whitespace_api.core.ratelimit import RateLimiter, limit
from whitespace_api.schemas.fba import FbaEstimate, FbaInput
from whitespace_api.schemas.trade import CountryOut
from whitespace_api.services import fba as service
from whitespace_api.services import fba_fees, freight, landed_cost
from whitespace_api.services import trade as trade_service

router = APIRouter(tags=["fba"])

_public_limit = RateLimiter(per_minute=10)
OPTIONS_CACHE_SECONDS = 86_400


class FbaCategory(BaseModel):
    key: fba_fees.CategoryKey
    label: str


class FbaOptions(BaseModel):
    categories: list[FbaCategory]
    origins: list[CountryOut] = Field(description="Countries we can price shipping from")
    fees_as_of: str
    plan_usd: float


async def _estimate(
    db: DbSession, client: HttpClient, settings: AppSettings, body: FbaInput
) -> FbaEstimate:
    try:
        return await service.estimate(db, client, body, settings=settings)
    except landed_cost.UnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except (trade_service.NotFoundError, landed_cost.NotCoveredError, freight.NoRouteError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except fba_fees.NotSupportedError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


@router.post("/fba/estimate", response_model=FbaEstimate, dependencies=[Depends(get_current_user)])
async def estimate(
    db: DbSession, client: HttpClient, settings: AppSettings, body: FbaInput
) -> FbaEstimate:
    """Profit per unit, margin, cash needed and a verdict for one product on Amazon US."""
    return await _estimate(db, client, settings, body)


@router.post("/public/fba/estimate", response_model=FbaEstimate)
async def public_estimate(
    request: Request, db: DbSession, client: HttpClient, settings: AppSettings, body: FbaInput
) -> FbaEstimate:
    """The same, signed out, for the free calculator: 10 a minute per visitor."""
    limit(_public_limit, request)
    return await _estimate(db, client, settings, body)


@router.get("/public/fba/options", response_model=FbaOptions)
async def options(response: Response, db: DbSession) -> FbaOptions:
    """Amazon categories, source countries and the fee table's date, for the form."""
    response.headers["Cache-Control"] = f"public, max-age={OPTIONS_CACHE_SECONDS}"
    return FbaOptions(
        categories=[FbaCategory(key=key, label=c.label) for key, c in fba_fees.CATEGORIES.items()],
        origins=await freight.origins_to(db, service.MARKET),
        fees_as_of=fba_fees.FEES_AS_OF,
        plan_usd=fba_fees.PROFESSIONAL_PLAN_USD,
    )
