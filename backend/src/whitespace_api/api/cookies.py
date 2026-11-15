"""Session cookies. One place decides names, paths, lifetimes and flags.

All cookies are httpOnly (page scripts can't read them), SameSite=Lax (not sent on
cross-site POSTs, which blocks CSRF), and Secure whenever the site runs on HTTPS.
"""

from __future__ import annotations

from typing import Any

from fastapi import Response

from whitespace_api.core.config import Settings
from whitespace_api.services.auth import Session

ACCESS_COOKIE = "ws_access"
REFRESH_COOKIE = "ws_refresh"
SESSION_COOKIE = "ws_session"
# The refresh cookie is only ever sent to the auth endpoints.
REFRESH_PATH = "/api/v1/auth"


def _flags(settings: Settings) -> dict[str, Any]:
    return {"httponly": True, "secure": settings.cookie_secure, "samesite": "lax"}


def set_session_cookies(response: Response, session: Session, settings: Settings) -> None:
    days = settings.refresh_token_days * 86400
    response.set_cookie(
        ACCESS_COOKIE,
        session.access_token,
        max_age=settings.access_token_minutes * 60,
        path="/",
        **_flags(settings),
    )
    response.set_cookie(
        REFRESH_COOKIE, session.refresh_token, max_age=days, path=REFRESH_PATH, **_flags(settings)
    )
    # Holds no secret: tells the frontend's route guard a session exists, since the
    # refresh cookie is only sent to /api/v1/auth and the access cookie expires quickly.
    response.set_cookie(SESSION_COOKIE, "1", max_age=days, path="/", **_flags(settings))


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH)
    response.delete_cookie(SESSION_COOKIE, path="/")


def safe_next_path(value: str | None, default: str = "/app") -> str:
    """Only same-site paths, so `?next=` can't send users to another website."""
    if value and value.startswith("/") and not value.startswith(("//", "/\\")):
        return value
    return default
