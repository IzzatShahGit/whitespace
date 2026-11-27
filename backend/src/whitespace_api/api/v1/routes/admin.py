"""Admin pages: usage overview, accounts, visits, and account actions. Admins only (404
for everyone else, so the pages don't appear to exist)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from whitespace_api.api.deps import AdminUser, AppSettings, DbSession
from whitespace_api.schemas.admin import (
    Segment,
    UserDetail,
    UserFilter,
    UserList,
    UserSort,
    UserUpdate,
    VisitFilter,
    VisitList,
)
from whitespace_api.schemas.analytics import AdminStats
from whitespace_api.services import admin as service
from whitespace_api.services import analytics

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStats)
async def stats(_: AdminUser, db: DbSession, settings: AppSettings) -> AdminStats:
    """Visitors, visits, sign-ups and feature use over the last 30 days."""
    return await analytics.summary(db, settings)


@router.get("/users", response_model=UserList)
async def users(
    _: AdminUser,
    db: DbSession,
    settings: AppSettings,
    q: Annotated[str, Query(max_length=100)] = "",
    segment: Segment = "real",
    status: UserFilter = "any",
    sort: UserSort = "joined",
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
) -> UserList:
    """Accounts, 50 a page. `segment`: real users, or test/demo/admin accounts."""
    return await service.list_users(
        db, settings, q=q, segment=segment, status=status, sort=sort, page=page
    )


@router.get("/users/{user_id}", response_model=UserDetail)
async def user(
    user_id: uuid.UUID, _: AdminUser, db: DbSession, settings: AppSettings
) -> UserDetail:
    """One account: profile, activity, what they made and their latest visits."""
    found = await service.user_detail(db, settings, user_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such account")
    return found


@router.patch("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_user(
    user_id: uuid.UUID, body: UserUpdate, admin: AdminUser, db: DbSession, settings: AppSettings
) -> Response:
    """Disable or enable an account (disabling signs it out everywhere at once), or mark
    it as a test/demo account."""
    try:
        found = await service.update_user(db, settings, admin, user_id, body)
    except service.AdminError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such account")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/users/{user_id}/sign-out", status_code=status.HTTP_204_NO_CONTENT)
async def sign_out(user_id: uuid.UUID, admin: AdminUser, db: DbSession) -> Response:
    """End every session of this account (within 15 minutes for open tabs)."""
    if not await service.sign_out_everywhere(db, admin, user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such account")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/visits", response_model=VisitList)
async def visits(
    _: AdminUser,
    db: DbSession,
    settings: AppSettings,
    show: VisitFilter = "all",
    country: Annotated[str | None, Query(max_length=2)] = None,
    source: Annotated[str | None, Query(max_length=60)] = None,
    include_test: bool = False,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
) -> VisitList:
    """Latest visits first: origin, device, pages in order and time on each."""
    return await service.list_visits(
        db,
        settings,
        show=show,
        country=country,
        source=source,
        include_test=include_test,
        page=page,
    )
