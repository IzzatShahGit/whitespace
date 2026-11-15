from fastapi import APIRouter

from whitespace_api.api.v1.routes import auth, google, health

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(google.router, tags=["auth"])
# Next: markets, products, briefs routers.
