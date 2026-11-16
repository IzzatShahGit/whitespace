"""Auth endpoints. Tokens travel only in httpOnly cookies, never in response bodies."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Response, status
from fastapi.responses import JSONResponse

from whitespace_api.api.cookies import clear_session_cookies, set_session_cookies
from whitespace_api.api.deps import AppSettings, CurrentUser, DbSession
from whitespace_api.schemas.auth import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    LoginRequest,
    ProvidersOut,
    RegisterRequest,
    UpdateMeRequest,
    UserOut,
)
from whitespace_api.services import auth as auth_service

router = APIRouter(prefix="/auth")


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
    return UserOut.model_validate(session.user)


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
    return UserOut.model_validate(session.user)


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
    return UserOut.model_validate(session.user)


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
    return ProvidersOut(password=True, google=settings.google_enabled)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
async def update_me(body: UpdateMeRequest, user: CurrentUser, db: DbSession) -> UserOut:
    return UserOut.model_validate(
        await auth_service.update_name(db, user, full_name=body.full_name)
    )


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
    return UserOut.model_validate(session.user)


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
