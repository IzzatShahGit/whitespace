"""Liveness and readiness checks used by Docker and the hosting platform."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api import __version__
from whitespace_api.core.db import get_session
from whitespace_api.schemas.health import HealthResponse, ReadinessResponse

log = logging.getLogger(__name__)

router = APIRouter(prefix="/health")


@router.get("", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    """The process is up. Does not touch the database."""
    return HealthResponse(status="ok", version=__version__)


@router.get("/ready", response_model=ReadinessResponse)
async def readiness(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReadinessResponse:
    """The API can serve traffic: the database answers."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        # The exception text names the cause (refused, bad password, unknown host) and
        # never contains the connection password.
        log.warning("database not reachable: %s: %s", type(exc).__name__, exc)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(status="unavailable", database="down")
    return ReadinessResponse(status="ok", database="up")
