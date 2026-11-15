"""AI market briefs. GET reads the current state; POST asks for one to be written."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status

from whitespace_api.api.deps import AppSettings, CurrentUser, DbSession, get_current_user
from whitespace_api.schemas.brief import BriefOut
from whitespace_api.services import briefs as brief_service
from whitespace_api.services import trade as trade_service
from whitespace_shared.gold import COUNTRY_CODE_PATTERN, HS6_PATTERN

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["briefs"])

Market = Annotated[str, Path(pattern=COUNTRY_CODE_PATTERN)]
Exporter = Annotated[str, Query(pattern=COUNTRY_CODE_PATTERN)]
HS6 = Annotated[str, Query(pattern=HS6_PATTERN)]


@router.get("/markets/{market}/brief", response_model=BriefOut)
async def get_brief(
    db: DbSession, settings: AppSettings, market: Market, exporter: Exporter, hs6: HS6
) -> BriefOut:
    """The brief if one exists ("missing" otherwise), or its progress while being written."""
    return await brief_service.get_brief(
        db, exporter=exporter, hs6=hs6, market=market, settings=settings
    )


@router.post("/markets/{market}/brief", response_model=BriefOut)
async def request_brief(
    response: Response,
    db: DbSession,
    user: CurrentUser,
    settings: AppSettings,
    market: Market,
    exporter: Exporter,
    hs6: HS6,
) -> BriefOut:
    """Write the brief (in the background) unless a fresh one already exists."""
    try:
        brief = await brief_service.request_brief(
            db, user, exporter=exporter, hs6=hs6, market=market, settings=settings
        )
    except trade_service.NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except brief_service.LimitError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc
    if brief.status == "pending":
        response.status_code = status.HTTP_202_ACCEPTED
    return brief
