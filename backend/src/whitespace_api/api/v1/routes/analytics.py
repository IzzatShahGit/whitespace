"""Usage analytics: anonymous page views in, a summary out (admins only)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from whitespace_api.api.deps import AppSettings, CurrentUser, DbSession
from whitespace_api.core.ratelimit import RateLimiter, client_key, limit
from whitespace_api.schemas.analytics import AdminStats, EventIn
from whitespace_api.services import analytics as service

router = APIRouter(tags=["analytics"])
_event_limit = RateLimiter(per_minute=120)


@router.post("/events", status_code=status.HTTP_204_NO_CONTENT)
async def track(body: EventIn, request: Request, db: DbSession, settings: AppSettings) -> Response:
    """Count one page view or action. No cookies; nothing that identifies a person."""
    limit(_event_limit, request)
    agent = request.headers.get("user-agent", "")[:300]
    if not service.is_bot(agent):
        path = service.page_pattern(body.path)
        visitor = (
            service.visitor_id(
                settings.jwt_secret.get_secret_value(), service.today(), client_key(request), agent
            )
            if body.event == "page_view"
            else None
        )
        await service.record(db, event=body.event, path=path, visitor=visitor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/admin/stats", response_model=AdminStats)
async def stats(user: CurrentUser, db: DbSession, settings: AppSettings) -> AdminStats:
    """Visitors, sign-ups and feature use over the last 30 days. Admins only."""
    if not settings.is_admin(user.email):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return await service.summary(db, settings)
