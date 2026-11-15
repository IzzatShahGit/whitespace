"""Sign in with Google. Browser-facing redirects; see services/google_oauth.py for the flow."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Cookie, Query
from fastapi.responses import RedirectResponse

from whitespace_api.api.cookies import safe_next_path, set_session_cookies
from whitespace_api.api.deps import AppSettings, DbSession
from whitespace_api.core.config import Settings
from whitespace_api.services import auth as auth_service
from whitespace_api.services import google_oauth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth/google")


def _to_app(settings: Settings, path: str) -> RedirectResponse:
    return RedirectResponse(settings.public_app_url.rstrip("/") + path, status_code=303)


def _failed(settings: Settings, reason: str) -> RedirectResponse:
    # Users only see a generic message; the reason goes to the logs.
    logger.warning("Google sign-in failed: %s", reason)
    response = _to_app(settings, "/login?error=google")
    response.delete_cookie(google_oauth.FLOW_COOKIE, path=google_oauth.FLOW_COOKIE_PATH)
    return response


@router.get("/start", response_class=RedirectResponse, status_code=303)
async def start(
    settings: AppSettings, next_path: Annotated[str | None, Query(alias="next")] = None
) -> RedirectResponse:
    """Send the browser to Google's account chooser."""
    try:
        flow = google_oauth.start_flow(settings, safe_next_path(next_path))
    except google_oauth.GoogleAuthError as exc:
        return _failed(settings, str(exc))
    response = RedirectResponse(flow.authorize_url, status_code=303)
    response.set_cookie(
        google_oauth.FLOW_COOKIE,
        flow.flow_cookie,
        max_age=int(google_oauth.FLOW_TTL.total_seconds()),
        path=google_oauth.FLOW_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",  # sent on Google's top-level redirect back to us
    )
    return response


@router.get("/callback", response_class=RedirectResponse, status_code=303)
async def callback(
    db: DbSession,
    settings: AppSettings,
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
    ws_oauth: Annotated[str | None, Cookie()] = None,
) -> RedirectResponse:
    """Google sends the browser back here. Verify everything, then sign in."""
    if error:  # e.g. the user pressed Cancel on Google's screen
        return _failed(settings, f"Google returned error={error[:64]!r}")
    try:
        flow = google_oauth.read_flow(ws_oauth, state, settings)
        if not code:
            raise google_oauth.GoogleAuthError("Missing authorization code")
        id_token = await google_oauth.exchange_code(code, flow["verifier"], settings)
        identity = await google_oauth.verify_id_token(id_token, flow["nonce"], settings)
        session = await auth_service.sign_in_with_google(db, identity, settings)
    except (google_oauth.GoogleAuthError, auth_service.AuthError) as exc:
        return _failed(settings, str(exc))

    response = _to_app(settings, safe_next_path(flow.get("next")))
    response.delete_cookie(google_oauth.FLOW_COOKIE, path=google_oauth.FLOW_COOKIE_PATH)
    set_session_cookies(response, session, settings)
    return response
