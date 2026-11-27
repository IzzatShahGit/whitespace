"""Usage analytics: page views and visits in. The admin summaries live in routes/admin.py."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response, status

from whitespace_api.api.deps import AppSettings, DbSession, OptionalUser
from whitespace_api.core.ratelimit import RateLimiter, client_key, limit
from whitespace_api.schemas.analytics import EventIn
from whitespace_api.services import analytics as service
from whitespace_api.services import geoip, visits

router = APIRouter(tags=["analytics"])
_event_limit = RateLimiter(per_minute=120)


@router.post("/events", status_code=status.HTTP_204_NO_CONTENT)
async def track(
    body: EventIn, request: Request, db: DbSession, settings: AppSettings, user: OptionalUser
) -> Response:
    """Count a page view or action, and add it to the visit. No cookies; the address is
    used for the day's visitor code and the country, then dropped."""
    limit(_event_limit, request)
    agent = request.headers.get("user-agent", "")[:300]
    if service.is_bot(agent):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    address = client_key(request)
    visitor = service.visitor_id(
        settings.jwt_secret.get_secret_value(), service.today(), address, agent
    )
    if body.event != "engage":  # time reports aren't page views or actions
        await service.record(
            db,
            event=body.event,
            path=service.page_pattern(body.path),
            visitor=visitor if body.event == "page_view" else None,
        )
    if body.event in ("page_view", "engage"):
        hit = visits.Hit(
            event=body.event,
            path=visits.journey_path(body.path),
            visitor=visitor,
            user_id=user.id if user else None,
            agent=agent,
            country=geoip.country(address, settings.geoip_path)
            if body.event == "page_view"
            else None,
            referrer=visits.referrer_host(body.referrer, request.headers.get("host", "")),
            utm_source=body.utm_source,
            utm_campaign=body.utm_campaign,
            seconds=body.seconds or 0,
        )
        await visits.record(db, hit, datetime.now(UTC))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
