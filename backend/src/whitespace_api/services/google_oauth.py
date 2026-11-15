"""Google sign-in: OpenID Connect authorization-code flow with PKCE.

Flow:
  1. /start   builds Google's consent URL with `state`, `nonce` and a PKCE challenge,
              and stores the matching secrets in a short-lived signed cookie.
  2. Google   sends the user back to /callback with `code` and `state`.
  3. /callback checks `state`, swaps `code` (+ PKCE verifier + client secret) for an
              ID token server-to-server, and verifies the token: Google's signature,
              issuer, audience, expiry, nonce and that Google verified the email.

Nothing from the browser is trusted except `code` and `state`, and both are checked.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
import jwt
from starlette.concurrency import run_in_threadpool

from whitespace_api.core.config import Settings

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 (URL, not a secret)
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ("https://accounts.google.com", "accounts.google.com")

CALLBACK_PATH = "/api/v1/auth/google/callback"
FLOW_COOKIE = "ws_oauth"
FLOW_COOKIE_PATH = "/api/v1/auth/google"
FLOW_TTL = timedelta(minutes=10)

# Caches Google's public signing keys between requests.
_jwks = jwt.PyJWKClient(JWKS_URL, cache_keys=True, lifespan=3600)


class GoogleAuthError(Exception):
    """Sign-in with Google failed. Details are for logs, never for users."""


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str
    email_verified: bool
    name: str


@dataclass(frozen=True)
class FlowStart:
    authorize_url: str
    flow_cookie: str  # signed; set as an httpOnly cookie on the redirect


def redirect_uri(settings: Settings) -> str:
    return settings.public_app_url.rstrip("/") + CALLBACK_PATH


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def start_flow(settings: Settings, next_path: str) -> FlowStart:
    if not settings.google_enabled:
        raise GoogleAuthError("Google sign-in is not configured")
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier, challenge = _pkce_pair()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri(settings),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    flow = {
        "type": "oauth",
        "state": state,
        "nonce": nonce,
        "verifier": verifier,
        "next": next_path,
        "exp": datetime.now(UTC) + FLOW_TTL,
    }
    cookie = jwt.encode(flow, settings.jwt_secret.get_secret_value(), algorithm="HS256")
    return FlowStart(authorize_url=f"{AUTHORIZE_URL}?{urlencode(params)}", flow_cookie=cookie)


def read_flow(cookie: str | None, state: str | None, settings: Settings) -> dict[str, str]:
    """The flow secrets, if the cookie is genuine, fresh and matches `state`."""
    if not cookie or not state:
        raise GoogleAuthError("Missing sign-in state")
    try:
        flow: dict[str, str] = jwt.decode(
            cookie, settings.jwt_secret.get_secret_value(), algorithms=["HS256"]
        )
    except jwt.PyJWTError as exc:
        raise GoogleAuthError("Sign-in state invalid or expired") from exc
    if flow.get("type") != "oauth" or not secrets.compare_digest(flow["state"], state):
        raise GoogleAuthError("Sign-in state mismatch")
    return flow


async def exchange_code(code: str, verifier: str, settings: Settings) -> str:
    """Swap the authorization code for Google's ID token (server to server)."""
    if settings.google_client_secret is None:
        raise GoogleAuthError("Google sign-in is not configured")
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret.get_secret_value(),
                "redirect_uri": redirect_uri(settings),
                "grant_type": "authorization_code",
                "code_verifier": verifier,
            },
        )
    if response.status_code != 200:
        raise GoogleAuthError(f"Token exchange failed: HTTP {response.status_code}")
    id_token = response.json().get("id_token")
    if not isinstance(id_token, str):
        raise GoogleAuthError("No ID token in Google's response")
    return id_token


async def verify_id_token(id_token: str, nonce: str, settings: Settings) -> GoogleIdentity:
    try:
        key = await run_in_threadpool(_jwks.get_signing_key_from_jwt, id_token)
        claims = jwt.decode(
            id_token,
            key.key,
            algorithms=["RS256"],
            audience=settings.google_client_id,
            options={"require": ["iss", "aud", "exp", "iat", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise GoogleAuthError(f"ID token rejected: {exc}") from exc
    if claims.get("iss") not in ISSUERS:
        raise GoogleAuthError("ID token from an unexpected issuer")
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise GoogleAuthError("ID token nonce mismatch")
    if not claims.get("email") or claims.get("email_verified") is not True:
        raise GoogleAuthError("Google account email is not verified")
    return GoogleIdentity(
        sub=str(claims["sub"]),
        email=str(claims["email"]).lower(),
        email_verified=True,
        name=str(claims.get("name") or claims["email"].split("@")[0])[:120],
    )
