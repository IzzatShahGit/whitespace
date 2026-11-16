"""Company leads: importers to sell to, or manufacturers to buy from, in one country."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status

from whitespace_api.api.deps import AppSettings, CurrentUser, DbSession, get_current_user
from whitespace_api.schemas.lead import IntroIn, IntroOut, LeadSide, LeadsOut
from whitespace_api.services import leads as service
from whitespace_shared.gold import COUNTRY_CODE_PATTERN, HS6_PATTERN

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["leads"])

Country = Annotated[str, Path(pattern=COUNTRY_CODE_PATTERN)]
HS6 = Annotated[str, Query(pattern=HS6_PATTERN)]
Side = Annotated[LeadSide, Query(description="buyers: importers there; suppliers: makers there")]


@router.get("/countries/{country}/leads", response_model=LeadsOut)
async def get_leads(
    db: DbSession, settings: AppSettings, country: Country, hs6: HS6, side: Side
) -> LeadsOut:
    """The company list if one exists ("missing" otherwise), or its progress."""
    return await service.get_leads(db, hs6=hs6, country=country, side=side, settings=settings)


@router.post("/countries/{country}/leads", response_model=LeadsOut)
async def request_leads(
    response: Response,
    db: DbSession,
    user: CurrentUser,
    settings: AppSettings,
    country: Country,
    hs6: HS6,
    side: Side,
) -> LeadsOut:
    """Search for companies (in the background) unless a fresh list already exists."""
    try:
        leads = await service.request_leads(
            db, user, hs6=hs6, country=country, side=side, settings=settings
        )
    except service.NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except service.LimitError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc
    if leads.status == "pending":
        response.status_code = status.HTTP_202_ACCEPTED
    return leads


@router.post("/leads/intro", response_model=IntroOut)
async def draft_intro(
    db: DbSession, user: CurrentUser, settings: AppSettings, body: IntroIn
) -> IntroOut:
    """A first-contact email to one company, ready to edit and send from your own inbox."""
    try:
        return await service.draft_intro(db, user, body, settings)
    except service.NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except service.LimitError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc
