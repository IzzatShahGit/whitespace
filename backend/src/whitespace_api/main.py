"""Application factory and entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from whitespace_api import __version__
from whitespace_api.api.v1.router import api_router
from whitespace_api.core.config import get_settings
from whitespace_api.core.db import get_engine
from whitespace_api.core.logging import configure_logging
from whitespace_api.services.recent import http_client


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
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
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("whitespace_api.main:app", host="0.0.0.0", port=8000, reload=True)  # noqa: S104
