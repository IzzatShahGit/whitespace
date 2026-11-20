"""Buyer checks: sanctions lists, registers, domains and scam wording, in one verdict."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from whitespace_api.api.deps import (
    AppSettings,
    CurrentUser,
    DbSession,
    HttpClient,
    get_current_user,
)
from whitespace_api.schemas.screening import BuyerCheckOut, CheckIn, ListInfo
from whitespace_api.services import buyer_check as service
from whitespace_api.services import screening
from whitespace_api.services.pipeline import LimitError, NotFoundError

router = APIRouter(
    prefix="/buyer-checks", dependencies=[Depends(get_current_user)], tags=["buyer checks"]
)


@router.post("", response_model=BuyerCheckOut)
async def check(
    body: CheckIn, db: DbSession, http: HttpClient, user: CurrentUser, settings: AppSettings
) -> BuyerCheckOut:
    """Check a company. With `contact_id`, its website and pasted replies are included
    and the result is kept on the pipeline card."""
    try:
        return await service.check(db, http, user, body, settings)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except LimitError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc


@router.get("/lists", response_model=list[ListInfo])
async def lists(db: DbSession) -> list[ListInfo]:
    """The sanctions lists we screen against, and when each was last loaded."""
    return [ListInfo(**vars(s)) for s in await screening.lists(db)]


@router.get("/contacts/{contact_id}", response_model=BuyerCheckOut)
async def latest(contact_id: uuid.UUID, db: DbSession, user: CurrentUser) -> BuyerCheckOut:
    """The last check of a pipeline contact."""
    try:
        return await service.latest(db, user, contact_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
