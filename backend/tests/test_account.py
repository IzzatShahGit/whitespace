"""Account settings: rename, change password (other sessions end), delete account."""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.seed import TOWELS
from whitespace_api.main import app
from whitespace_api.models import User, UserProfile

PASSWORD = "towels-2026!"


async def test_account_endpoints_require_sign_in(client: AsyncClient) -> None:
    assert (await client.patch("/api/v1/auth/me", json={"full_name": "X"})).status_code == 401
    assert (
        await client.post("/api/v1/auth/password", json={"new_password": "x" * 8})
    ).status_code == 401
    assert (await client.post("/api/v1/auth/delete-account", json={})).status_code == 401


async def test_rename(user: AsyncClient) -> None:
    response = await user.patch("/api/v1/auth/me", json={"full_name": "  Ahmed Khan  "})
    assert response.status_code == 200 and response.json()["full_name"] == "Ahmed Khan"
    assert (await user.get("/api/v1/auth/me")).json()["full_name"] == "Ahmed Khan"
    assert (await user.patch("/api/v1/auth/me", json={"full_name": ""})).status_code == 422


async def test_change_password_needs_the_current_one(user: AsyncClient) -> None:
    assert (await user.get("/api/v1/auth/me")).json()["has_password"] is True
    wrong = await user.post(
        "/api/v1/auth/password", json={"current_password": "nope", "new_password": "fresh-pass-1"}
    )
    assert wrong.status_code == 403
    ok = await user.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": "fresh-pass-1"},
    )
    assert ok.status_code == 200
    login = await user.post(
        "/api/v1/auth/login", json={"email": "ahmed@example.com", "password": "fresh-pass-1"}
    )
    assert login.status_code == 200


async def test_change_password_signs_out_other_sessions(
    user: AsyncClient, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        await other.post(
            "/api/v1/auth/login", json={"email": "ahmed@example.com", "password": PASSWORD}
        )
        await user.post(
            "/api/v1/auth/password",
            json={"current_password": PASSWORD, "new_password": "fresh-pass-1"},
        )
        assert (await other.post("/api/v1/auth/refresh")).status_code == 401
    assert (await user.post("/api/v1/auth/refresh")).status_code == 200  # this device stays in


async def test_delete_account_removes_everything(
    user: AsyncClient, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    profile = {"exporter": "PAK", "role": "exporter", "products": [TOWELS], "current_markets": []}
    assert (await user.put("/api/v1/me/profile", json=profile)).status_code == 200
    assert (
        await user.post("/api/v1/auth/delete-account", json={"password": "nope"})
    ).status_code == 403
    response = await user.post("/api/v1/auth/delete-account", json={"password": PASSWORD})
    assert response.status_code == 204
    assert (await user.get("/api/v1/auth/me")).status_code == 401
    async with db_sessionmaker() as db:
        assert await db.scalar(select(func.count()).select_from(User)) == 0
        assert await db.scalar(select(func.count()).select_from(UserProfile)) == 0
