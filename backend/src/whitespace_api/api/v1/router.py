from fastapi import APIRouter

from whitespace_api.api.v1.routes import (
    analytics,
    auth,
    briefs,
    chat,
    freight,
    fx,
    google,
    health,
    landed_cost,
    leads,
    me,
    pipeline,
    public,
    quotes,
    requirements,
    shipments,
    sourcing,
    tenders,
    trade,
    watches,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(google.router, tags=["auth"])
api_router.include_router(trade.router)
api_router.include_router(landed_cost.router)
api_router.include_router(freight.router)
api_router.include_router(me.router)
api_router.include_router(briefs.router)
api_router.include_router(sourcing.router)
api_router.include_router(leads.router)
api_router.include_router(fx.router)
api_router.include_router(chat.router)
api_router.include_router(watches.router)
api_router.include_router(public.router)
api_router.include_router(analytics.router)
api_router.include_router(requirements.router)
api_router.include_router(pipeline.router)
api_router.include_router(quotes.router)
api_router.include_router(tenders.router)
api_router.include_router(shipments.router)
