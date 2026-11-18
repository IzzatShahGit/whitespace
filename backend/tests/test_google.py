"""Google sign-in. Google itself is never called: the token exchange is faked, and ID
tokens are signed with a throwaway RSA key so signature checks are real."""

from __future__ import annotations

import time
from collections.abc import Iterator
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import AsyncClient

from whitespace_api.core.config import Settings, get_settings
from whitespace_api.main import app
from whitespace_api.services import google_oauth

CLIENT_ID = "test-client.apps.googleusercontent.com"
SETTINGS = Settings(google_client_id=CLIENT_ID, google_client_secret="test-secret")  # type: ignore[arg-type]
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(autouse=True)
def google_configured(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    app.dependency_overrides[get_settings] = lambda: SETTINGS
    monkeypatch.setattr(
        google_oauth._jwks,
        "get_signing_key_from_jwt",
        lambda _token: SimpleNamespace(key=KEY.public_key()),
    )
    yield
    app.dependency_overrides.pop(get_settings, None)


def id_token(**overrides: object) -> str:
    now = int(time.time())
    claims: dict[str, object] = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "google-123",
        "email": "Sara@Example.com",
        "email_verified": True,
        "name": "Sara Malik",
        "iat": now,
        "exp": now + 300,
    }
    claims.update(overrides)
    return jwt.encode(claims, KEY, algorithm="RS256")


async def start(client: AsyncClient) -> dict[str, str]:
    """Run /start; return Google's query params (state, nonce, ...)."""
    response = await client.get("/api/v1/auth/google/start", params={"next": "/app"})
    assert response.status_code == 303
    location = urlparse(response.headers["location"])
    assert location.netloc == "accounts.google.com"
    return {k: v[0] for k, v in parse_qs(location.query).items()}


def fake_google(monkeypatch: pytest.MonkeyPatch, **claims: object) -> None:
    """Make the token exchange return a signed ID token for the flow's nonce."""

    async def exchange(code: str, verifier: str, settings: Settings) -> str:
        assert code == "auth-code" and verifier
        return id_token(**{"nonce": fake_google.nonce, **claims})  # type: ignore[attr-defined]

    monkeypatch.setattr(google_oauth, "exchange_code", exchange)


async def finish(client: AsyncClient, monkeypatch: pytest.MonkeyPatch, **claims: object):  # type: ignore[no-untyped-def]
    params = await start(client)
    fake_google.nonce = params["nonce"]  # type: ignore[attr-defined]
    fake_google(monkeypatch, **claims)
    return await client.get(
        "/api/v1/auth/google/callback", params={"code": "auth-code", "state": params["state"]}
    )


async def test_providers_reports_google(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/providers")
    assert response.json() == {"password": True, "google": True, "password_reset": False}


async def test_start_uses_pkce_state_and_nonce(client: AsyncClient) -> None:
    params = await start(client)
    assert params["code_challenge_method"] == "S256"
    assert params["state"] and params["nonce"] and params["code_challenge"]
    assert params["redirect_uri"] == "http://localhost:3400/api/v1/auth/google/callback"
    assert client.cookies.get("ws_oauth")


async def test_new_google_user_is_created_and_signed_in(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    response = await finish(client, monkeypatch)
    assert response.status_code == 303
    assert response.headers["location"] == "http://localhost:3400/app"
    me = (await client.get("/api/v1/auth/me")).json()
    assert me["email"] == "sara@example.com" and me["email_verified"] is True
    assert me["full_name"] == "Sara Malik"


async def test_state_mismatch_is_rejected(client: AsyncClient) -> None:
    await start(client)
    response = await client.get(
        "/api/v1/auth/google/callback", params={"code": "auth-code", "state": "forged"}
    )
    assert response.headers["location"].endswith("/login?error=google")
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_missing_flow_cookie_is_rejected(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/auth/google/callback", params={"code": "auth-code", "state": "anything"}
    )
    assert response.headers["location"].endswith("/login?error=google")


@pytest.mark.parametrize(
    "claims",
    [
        {"aud": "someone-elses-client"},
        {"iss": "https://evil.example"},
        {"email_verified": False},
        {"exp": int(time.time()) - 10},
    ],
)
async def test_bad_id_tokens_are_rejected(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, claims: dict[str, object]
) -> None:
    response = await finish(client, monkeypatch, **claims)
    assert response.headers["location"].endswith("/login?error=google")


async def test_wrong_nonce_is_rejected(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    response = await finish(client, monkeypatch, nonce="replayed-token")
    assert response.headers["location"].endswith("/login?error=google")


async def test_pre_hijacked_account_loses_attackers_password(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An attacker registers the victim's email with a password first...
    await client.post(
        "/api/v1/auth/register",
        json={"email": "sara@example.com", "full_name": "Attacker", "password": "attacker-pw-1"},
    )
    attacker_refresh = client.cookies.get("ws_refresh")
    client.cookies.clear()

    # ...then the real owner signs in with Google.
    assert (await finish(client, monkeypatch)).status_code == 303

    # The attacker's password and session no longer work.
    login = await client.post(
        "/api/v1/auth/login", json={"email": "sara@example.com", "password": "attacker-pw-1"}
    )
    assert login.status_code == 401
    client.cookies.clear()
    client.cookies.set("ws_refresh", attacker_refresh, path="/api/v1/auth")
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


async def test_unconfigured_google_redirects_with_error(client: AsyncClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)  # type: ignore[call-arg]
    response = await client.get("/api/v1/auth/google/start")
    assert response.headers["location"].endswith("/login?error=google")
    assert (await client.get("/api/v1/auth/providers")).json()["google"] is False
