"""Application factory and entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from whitespace_api import __version__
from whitespace_api.api.v1.router import api_router
from whitespace_api.core import scheduler
from whitespace_api.core.config import get_settings
from whitespace_api.core.db import get_engine
from whitespace_api.core.http import http_client
from whitespace_api.core.logging import configure_logging
from whitespace_api.core.tasks import wait_for_jobs
from whitespace_api.jobs import scheduled_jobs

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    # Shows in the host's logs which database this process uses (never the password).
    log.info("app_env=%s database=%s", settings.app_env, settings.database_target)
    scheduler.start(scheduled_jobs(), settings)
    yield
    await scheduler.stop()
    await wait_for_jobs()  # let in-flight briefs and replies finish before shutting down
    await http_client().aclose()
    await get_engine().dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Whitespace API",
        version=__version__,
        description="Ranks export markets for a product and an exporter country.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("whitespace_api.main:app", host="0.0.0.0", port=8000, reload=True)  # noqa: S104
