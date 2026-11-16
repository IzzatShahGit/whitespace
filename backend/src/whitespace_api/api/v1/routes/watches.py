"""Watchlists and the notifications they produce (the bell). All require sign-in, and
users only ever see and change their own."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from whitespace_api.api.deps import AppSettings, CurrentUser, DbSession, get_current_user
from whitespace_api.schemas.watch import (
    MarkReadIn,
    NotificationsPage,
    UnreadCount,
    WatchIn,
    WatchOut,
    WatchStatus,
)
from whitespace_api.services import watches as watch_service
from whitespace_shared.gold import COUNTRY_CODE_PATTERN, HS6_PATTERN

router = APIRouter(dependencies=[Depends(get_current_user)])

Country = Annotated[str, Query(pattern=COUNTRY_CODE_PATTERN, description="ISO code, e.g. DEU")]
HS6 = Annotated[str, Query(pattern=HS6_PATTERN, description="Six-digit product code")]
Exporter = Annotated[
    str | None, Query(pattern=COUNTRY_CODE_PATTERN, description="Defaults to your country")
]


@router.get("/watches", response_model=list[WatchOut], tags=["watches"])
async def list_watches(db: DbSession, user: CurrentUser, settings: AppSettings) -> list[WatchOut]:
    """Your watched product-markets, newest first."""
    return await watch_service.list_watches(db, user, settings)


@router.post(
    "/watches",
    response_model=WatchOut,
    status_code=status.HTTP_201_CREATED,
    tags=["watches"],
    responses={
        200: {"model": WatchOut, "description": "Already watching: the existing watch"},
        409: {"description": "Watch limit reached"},
        422: {"description": "Not a ranked market for this product and exporter"},
    },
)
async def add_watch(
    body: WatchIn, response: Response, db: DbSession, user: CurrentUser, settings: AppSettings
) -> WatchOut:
    """Watch a product in a market, to be notified when monthly data shows a big move."""
    try:
        watch, created = await watch_service.add_watch(db, user, body, settings)
    except watch_service.InvalidWatchError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except watch_service.WatchLimitError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if not created:
        response.status_code = status.HTTP_200_OK
    return watch


@router.get("/watches/check", response_model=WatchStatus, tags=["watches"])
async def check_watch(
    db: DbSession, user: CurrentUser, hs6: HS6, market: Country, exporter: Exporter = None
) -> WatchStatus:
    """Whether you watch this product-market (for a watch toggle)."""
    return await watch_service.watch_status(db, user, exporter=exporter, hs6=hs6, market=market)


@router.delete(
    "/watches/{watch_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["watches"],
    responses={404: {"description": "No such watch (or not yours)"}},
)
async def delete_watch(watch_id: uuid.UUID, db: DbSession, user: CurrentUser) -> Response:
    """Stop watching."""
    try:
        await watch_service.delete_watch(db, user, watch_id)
    except watch_service.WatchNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/notifications", response_model=NotificationsPage, tags=["notifications"])
async def list_notifications(
    db: DbSession, user: CurrentUser, limit: Annotated[int, Query(ge=1, le=100)] = 20
) -> NotificationsPage:
    """Your newest notifications, and how many are unread in all."""
    return await watch_service.list_notifications(db, user, limit=limit)


@router.post("/notifications/read", response_model=UnreadCount, tags=["notifications"])
async def mark_read(body: MarkReadIn, db: DbSession, user: CurrentUser) -> UnreadCount:
    """Mark notifications read (`ids`, or `all: true`). Returns the new unread count."""
    return await watch_service.mark_read(db, user, body)
