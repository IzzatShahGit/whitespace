"""Auth endpoints. Tokens travel only in httpOnly cookies, never in response bodies."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from whitespace_api.api.cookies import clear_session_cookies, set_session_cookies
from whitespace_api.api.deps import AppSettings, CurrentUser, DbSession
from whitespace_api.core.config import Settings
from whitespace_api.core.ratelimit import RateLimiter, limit
from whitespace_api.models.user import User
from whitespace_api.schemas.auth import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    DigestIn,
    DigestOut,
    ForgotPasswordRequest,
    LocaleIn,
    LoginRequest,
    ProvidersOut,
    RegisterRequest,
    ResetPasswordRequest,
    TokenIn,
    UnsubscribeIn,
    UpdateMeRequest,
    UserOut,
)
from whitespace_api.services import auth as auth_service
from whitespace_api.services import digest as digest_service

router = APIRouter(prefix="/auth")


def _out(user: User, settings: Settings) -> UserOut:
    """The user as the app sees them, including whether they're an admin."""
    return UserOut.model_validate(user).model_copy(
        update={"is_admin": settings.is_admin(user.email)}
    )


_reset_limit = RateLimiter(per_minute=5)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest, response: Response, db: DbSession, settings: AppSettings
) -> UserOut:
    try:
        session = await auth_service.register(
            db,
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            settings=settings,
        )
    except auth_service.EmailTakenError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    set_session_cookies(response, session, settings)
    return _out(session.user, settings)


@router.post("/login", response_model=UserOut)
async def login(
    body: LoginRequest, response: Response, db: DbSession, settings: AppSettings
) -> UserOut:
    try:
        session = await auth_service.login(
            db, email=body.email, password=body.password, settings=settings
        )
    except auth_service.AuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    set_session_cookies(response, session, settings)
    return _out(session.user, settings)


@router.post("/refresh", response_model=UserOut)
async def refresh(
    response: Response,
    db: DbSession,
    settings: AppSettings,
    ws_refresh: Annotated[str | None, Cookie()] = None,
) -> UserOut | JSONResponse:
    try:
        if not ws_refresh:
            raise auth_service.AuthError("Not signed in")
        session = await auth_service.refresh(db, refresh_token=ws_refresh, settings=settings)
    except auth_service.AuthError as exc:
        failure = JSONResponse({"detail": str(exc)}, status_code=status.HTTP_401_UNAUTHORIZED)
        clear_session_cookies(failure)
        return failure
    set_session_cookies(response, session, settings)
    return _out(session.user, settings)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    db: DbSession,
    ws_refresh: Annotated[str | None, Cookie()] = None,
) -> None:
    await auth_service.logout(db, refresh_token=ws_refresh)
    clear_session_cookies(response)


@router.get("/providers", response_model=ProvidersOut)
async def providers(settings: AppSettings) -> ProvidersOut:
    """Which sign-in methods are available, so the UI only shows working buttons."""
    return ProvidersOut(
        password=True, google=settings.google_enabled, password_reset=settings.email_enabled
    )


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser, settings: AppSettings) -> UserOut:
    return _out(user, settings)


@router.patch("/me", response_model=UserOut)
async def update_me(
    body: UpdateMeRequest, user: CurrentUser, db: DbSession, settings: AppSettings
) -> UserOut:
    return _out(await auth_service.update_name(db, user, full_name=body.full_name), settings)


@router.put("/me/locale", response_model=UserOut)
async def set_locale(
    body: LocaleIn, user: CurrentUser, db: DbSession, settings: AppSettings
) -> UserOut:
    """The interface language, kept with the account so every device uses it."""
    user.locale = body.locale
    await db.commit()
    return _out(user, settings)


@router.post("/password", response_model=UserOut)
async def change_password(
    body: ChangePasswordRequest,
    response: Response,
    user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
) -> UserOut:
    """Change (or, for Google-only accounts, set) the password. Other sessions are signed out."""
    try:
        session = await auth_service.change_password(
            db,
            user,
            current_password=body.current_password,
            new_password=body.new_password,
            settings=settings,
        )
    except auth_service.AuthError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    set_session_cookies(response, session, settings)
    return _out(session.user, settings)


@router.post("/password/forgot", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    body: ForgotPasswordRequest, request: Request, db: DbSession, settings: AppSettings
) -> None:
    """Email a reset link if the account exists. The answer is the same either way."""
    limit(_reset_limit, request)
    if not settings.email_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Password reset isn't available")
    await auth_service.request_password_reset(db, email=body.email, settings=settings)


@router.post("/password/reset", response_model=UserOut)
async def reset_password(
    body: ResetPasswordRequest,
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
) -> UserOut:
    """Set a new password from an emailed link, and sign in. Other sessions end."""
    limit(_reset_limit, request)
    try:
        session = await auth_service.reset_password(
            db, token=body.token, new_password=body.new_password, settings=settings
        )
    except auth_service.AuthError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    set_session_cookies(response, session, settings)
    return _out(session.user, settings)


@router.post("/digest", response_model=DigestOut)
async def set_digest(
    body: DigestIn, user: CurrentUser, db: DbSession, settings: AppSettings
) -> DigestOut:
    """Turn the weekly email on or off. An unverified address gets a confirmation link."""
    if body.enabled and not settings.email_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Email isn't set up yet")
    try:
        enabled, sent = await auth_service.set_digest(
            db, user, enabled=body.enabled, settings=settings
        )
    except auth_service.AuthError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc
    return DigestOut(digest_enabled=enabled, verification_sent=sent)


@router.post("/verify-email", response_model=UserOut)
async def verify_email(
    body: TokenIn, request: Request, db: DbSession, settings: AppSettings
) -> UserOut:
    """Confirm an address from the emailed link (works signed in or out)."""
    limit(_reset_limit, request)
    try:
        user = await auth_service.verify_email(db, token=body.token)
    except auth_service.AuthError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return _out(user, settings)


@router.post("/unsubscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(
    body: UnsubscribeIn, request: Request, db: DbSession, settings: AppSettings
) -> None:
    """Stop the weekly email, from the link in it (no sign-in needed)."""
    limit(_reset_limit, request)
    if not digest_service.valid_unsubscribe(body.u, body.t, settings):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This unsubscribe link isn't valid")
    await auth_service.unsubscribe(db, body.u)


@router.post("/delete-account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    body: DeleteAccountRequest, response: Response, user: CurrentUser, db: DbSession
) -> None:
    """Permanently delete the account, its profile, conversations and watches."""
    try:
        await auth_service.delete_account(db, user, password=body.password)
    except auth_service.AuthError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    clear_session_cookies(response)
