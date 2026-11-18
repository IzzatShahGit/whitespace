"""Open EU public tenders for your products, and company register checks."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from whitespace_api.api.deps import CurrentUser, DbSession, HttpClient, get_current_user
from whitespace_api.core.ratelimit import RateLimiter
from whitespace_api.schemas.tenders import CompanyCheck, TendersOut, VatCheck, VatIn
from whitespace_api.services import tenders as service
from whitespace_shared.gold import COUNTRY_CODE_PATTERN, HS6_PATTERN

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["tenders"])
_checks = RateLimiter(per_minute=20)  # per user: the registers are shared public services


def _limit(user_id: object) -> None:
    if not _checks.allow(f"user:{user_id}"):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many checks. Wait a minute.")


@router.get("/tenders", response_model=TendersOut)
async def my_tenders(db: DbSession, http: HttpClient, user: CurrentUser) -> TendersOut:
    """Open EU tenders for the products in your profile, soonest deadline first."""
    return await service.for_user(db, http, user)


@router.get("/tenders/{hs6}", response_model=TendersOut)
async def product_tenders(
    db: DbSession, http: HttpClient, hs6: Annotated[str, Path(pattern=HS6_PATTERN)]
) -> TendersOut:
    try:
        found, fetched, stale, name = await service.for_product(db, http, hs6)
    except service.NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except service.UnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return TendersOut(tenders=found, fetched_at=fetched, stale=stale, products=[name])


@router.get("/companies/check", response_model=CompanyCheck)
async def check_company(
    db: DbSession,
    http: HttpClient,
    user: CurrentUser,
    name: Annotated[str, Query(min_length=2, max_length=160)],
    country: Annotated[str, Query(pattern=COUNTRY_CODE_PATTERN)],
) -> CompanyCheck:
    """Look a company up in the global register of legal entities (GLEIF)."""
    _limit(user.id)
    try:
        return await service.check_company(db, http, name, country)
    except service.NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post("/companies/vat", response_model=VatCheck)
async def check_vat(body: VatIn, http: HttpClient, user: CurrentUser) -> VatCheck:
    """Check an EU VAT number with the EU's VIES service."""
    _limit(user.id)
    try:
        return await service.check_vat(http, body.country, body.number)
    except service.NotFoundError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except service.UnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
