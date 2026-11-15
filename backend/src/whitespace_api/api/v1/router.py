from fastapi import APIRouter

from whitespace_api.api.v1.routes import auth, briefs, chat, fx, google, health, me, sourcing, trade

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(google.router, tags=["auth"])
api_router.include_router(trade.router)
api_router.include_router(me.router)
api_router.include_router(briefs.router)
api_router.include_router(sourcing.router)
api_router.include_router(fx.router)
api_router.include_router(chat.router)
