"""Test fixtures. Database tests use a separate `whitespace_test` database.

Locally that is the Docker Postgres on :5440 (`make db`); in CI, a service container.
Database tests are skipped if Postgres isn't reachable.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from whitespace_api.core.config import Settings, get_settings
from whitespace_api.core.db import get_session
from whitespace_api.main import app
from whitespace_api.models import Base

ADMIN_DSN = os.getenv(
    "TEST_DATABASE_ADMIN_DSN", "postgresql://whitespace:whitespace@localhost:5440/whitespace"
)
TEST_DB = "whitespace_test"
TEST_URL = ADMIN_DSN.rsplit("/", 1)[0].replace("postgresql://", "postgresql+asyncpg://") + (
    f"/{TEST_DB}"
)


async def _ensure_test_database() -> None:
    conn = await asyncpg.connect(ADMIN_DSN, timeout=3)
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", TEST_DB)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{TEST_DB}"')
    finally:
        await conn.close()


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings never come from the developer's shell: drop any exported app variables."""
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)


@pytest.fixture
async def db_sessionmaker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    try:
        await _ensure_test_database()
    except (OSError, asyncpg.PostgresError, TimeoutError):
        pytest.skip("Postgres not reachable on :5440; run `make db`")
    engine = create_async_engine(TEST_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        # Rebuild from the current models every test: always the latest schema, no leftovers.
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def client(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    async def _session() -> AsyncIterator[AsyncSession]:
        async with db_sessionmaker() as session:
            yield session

    app.dependency_overrides[get_session] = _session
    # Tests never read the developer's .env (real keys there would change behaviour).
    app.dependency_overrides.setdefault(get_settings, lambda: Settings(_env_file=None))  # type: ignore[call-arg]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
