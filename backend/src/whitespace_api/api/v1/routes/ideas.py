"""Product ideas for Amazon sellers: public (it's also the landing page's best hook)."""

from __future__ import annotations

from fastapi import APIRouter, Response

from whitespace_api.api.deps import DbSession
from whitespace_api.schemas.ideas import IdeasOut
from whitespace_api.services import ideas as service

router = APIRouter(tags=["ideas"])

# Lists change weekly and import data monthly; a short cache keeps the page instant.
CACHE_SECONDS = 900


@router.get("/public/ideas", response_model=IdeasOut)
async def ideas(response: Response, db: DbSession) -> IdeasOut:
    """Amazon's best sellers this week and the fastest-growing US imports, with sources."""
    response.headers["Cache-Control"] = f"public, max-age={CACHE_SECONDS}"
    return await service.ideas(db)
