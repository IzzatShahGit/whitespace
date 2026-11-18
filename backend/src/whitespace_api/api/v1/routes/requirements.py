"""Import requirements for a lane, and the user's checklist."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status

from whitespace_api.api.deps import AppSettings, CurrentUser, DbSession, get_current_user
from whitespace_api.schemas.requirements import RequirementsOut
from whitespace_api.services import requirements as service
from whitespace_shared.gold import COUNTRY_CODE_PATTERN, HS6_PATTERN

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["requirements"])

Market = Annotated[str, Path(pattern=COUNTRY_CODE_PATTERN)]
HS6 = Annotated[str, Query(pattern=HS6_PATTERN)]
Exporter = Annotated[str, Query(pattern=COUNTRY_CODE_PATTERN, description="Shipping from")]
Item = Annotated[str, Path(pattern=r"^[0-9a-f]{16}$")]


@router.get("/markets/{market}/requirements", response_model=RequirementsOut)
async def get_requirements(
    db: DbSession, user: CurrentUser, settings: AppSettings, market: Market, hs6: HS6,
    exporter: Exporter,
) -> RequirementsOut:  # fmt: skip
    """The researched requirements ("missing" if never checked), with your ticks."""
    return await service.get_requirements(
        db, user, hs6=hs6, market=market, exporter=exporter, settings=settings
    )


@router.post("/markets/{market}/requirements", response_model=RequirementsOut)
async def request_requirements(
    response: Response, db: DbSession, user: CurrentUser, settings: AppSettings,
    market: Market, hs6: HS6, exporter: Exporter,
) -> RequirementsOut:  # fmt: skip
    """Research the requirements in the background unless a fresh result exists."""
    try:
        out = await service.request_requirements(
            db, user, hs6=hs6, market=market, exporter=exporter, settings=settings
        )
    except service.NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except service.LimitError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc
    if out.status == "pending":
        response.status_code = status.HTTP_202_ACCEPTED
    return out


@router.put("/markets/{market}/requirements/done/{item}", status_code=status.HTTP_204_NO_CONTENT)
async def tick(db: DbSession, user: CurrentUser, market: Market, item: Item, hs6: HS6) -> None:
    """Mark one requirement as done (idempotent)."""
    await service.set_done(db, user, hs6=hs6, market=market, item=item, value=True)


@router.delete("/markets/{market}/requirements/done/{item}", status_code=status.HTTP_204_NO_CONTENT)
async def untick(db: DbSession, user: CurrentUser, market: Market, item: Item, hs6: HS6) -> None:
    await service.set_done(db, user, hs6=hs6, market=market, item=item, value=False)
