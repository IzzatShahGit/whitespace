"""Password reset: an emailed one-time link sets a new password and ends old sessions."""

from __future__ import annotations

import re
from collections.abc import Iterator

import pytest
from httpx import AsyncClient
from pydantic import SecretStr

from whitespace_api.api.v1.routes import auth as auth_routes
from whitespace_api.core import tasks
from whitespace_api.core.config import Settings, get_settings
from whitespace_api.core.ratelimit import RateLimiter
from whitespace_api.main import app
from whitespace_api.notify.email import EmailMessage
from whitespace_api.services import auth as auth_service

EMAIL = "ahmed@example.com"


class Inbox:
    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.messages.append(message)

    def token(self) -> str:
        found = re.search(r"reset-password\?token=(\S+)", self.messages[-1].text)
        assert found
        return found.group(1)


@pytest.fixture
def inbox(monkeypatch: pytest.MonkeyPatch) -> Iterator[Inbox]:
    box = Inbox()
    monkeypatch.setattr(auth_service, "get_sender", lambda _settings: box)
    monkeypatch.setattr(auth_routes, "_reset_limit", RateLimiter(per_minute=1000))
    app.dependency_overrides[get_settings] = lambda: Settings(  # type: ignore[call-arg]
        _env_file=None, smtp_user="whitespace@example.com", smtp_password=SecretStr("app-pass")
    )
    yield box


async def forgot(client: AsyncClient, email: str) -> int:
    response = await client.post("/api/v1/auth/password/forgot", json={"email": email})
    await tasks.wait_for_jobs()
    return response.status_code


async def test_off_without_an_email_account(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/auth/providers")).json()["password_reset"] is False
    assert (await forgot(client, EMAIL)) == 503


async def test_reset_flow(user: AsyncClient, inbox: Inbox) -> None:
    """`user` is the signed-in test client; the reset happens as if from another device."""
    old_refresh = user.cookies["ws_refresh"]
    assert (await user.get("/api/v1/auth/providers")).json()["password_reset"] is True
    assert (await forgot(user, EMAIL)) == 202
    assert len(inbox.messages) == 1 and inbox.messages[0].to == EMAIL
    token = inbox.token()

    short = await user.post(
        "/api/v1/auth/password/reset", json={"token": token, "new_password": "short"}
    )
    assert short.status_code == 422
    done = await user.post(
        "/api/v1/auth/password/reset", json={"token": token, "new_password": "brand-new-pass"}
    )
    assert done.status_code == 200 and done.json()["email_verified"] is True
    assert done.cookies.get("ws_refresh") not in (None, old_refresh)  # signed in afresh

    again = await user.post(
        "/api/v1/auth/password/reset", json={"token": token, "new_password": "another-pass-1"}
    )
    assert again.status_code == 400  # one use only
    user.cookies.set("ws_refresh", old_refresh)
    assert (await user.post("/api/v1/auth/refresh")).status_code == 401  # old session ended
    old = await user.post("/api/v1/auth/login", json={"email": EMAIL, "password": "towels-2026!"})
    assert old.status_code == 401
    new = await user.post("/api/v1/auth/login", json={"email": EMAIL, "password": "brand-new-pass"})
    assert new.status_code == 200


async def test_unknown_emails_look_the_same(client: AsyncClient, inbox: Inbox) -> None:
    assert (await forgot(client, "nobody@example.com")) == 202
    assert inbox.messages == []


async def test_links_per_hour_are_capped(user: AsyncClient, inbox: Inbox) -> None:
    for _ in range(auth_service.RESETS_PER_HOUR + 2):
        assert (await forgot(user, EMAIL)) == 202
    assert len(inbox.messages) == auth_service.RESETS_PER_HOUR
    bad = await user.post(
        "/api/v1/auth/password/reset", json={"token": "x" * 40, "new_password": "brand-new-pass"}
    )
    assert bad.status_code == 400
