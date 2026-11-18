"""Quotes and proforma invoices, and the business details printed on them."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from whitespace_api.api.deps import (
    AppSettings,
    CurrentUser,
    DbSession,
    HttpClient,
    get_current_user,
)
from whitespace_api.schemas.quotes import BusinessIn, BusinessOut, QuoteIn, QuoteOut, QuoteSummary
from whitespace_api.services import quotes as service

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["quotes"])


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, service.NotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


ERRORS = (service.NotFoundError, service.QuoteError)


@router.get("/business", response_model=BusinessOut)
async def get_business(db: DbSession, user: CurrentUser) -> BusinessOut:
    return await service.get_business(db, user)


@router.put("/business", response_model=BusinessOut)
async def save_business(body: BusinessIn, db: DbSession, user: CurrentUser) -> BusinessOut:
    """Your company as printed on quotes and proformas."""
    return await service.save_business(db, user, body)


@router.post("/quotes/preview", response_model=QuoteOut)
async def preview(
    body: QuoteIn, db: DbSession, http: HttpClient, user: CurrentUser, settings: AppSettings
) -> QuoteOut:
    """Price a quote without issuing it (no number, nothing saved)."""
    try:
        return await service.price(db, http, user, body, settings)
    except ERRORS as exc:
        raise _http(exc) from exc


@router.post("/quotes", response_model=QuoteOut, status_code=status.HTTP_201_CREATED)
async def create(
    body: QuoteIn, db: DbSession, http: HttpClient, user: CurrentUser, settings: AppSettings
) -> QuoteOut:
    """Issue a quote or proforma: numbered, and saved exactly as priced."""
    try:
        return await service.create(db, http, user, body, settings)
    except ERRORS as exc:
        raise _http(exc) from exc


@router.get("/quotes", response_model=list[QuoteSummary])
async def list_quotes(db: DbSession, user: CurrentUser) -> list[QuoteSummary]:
    return await service.list_quotes(db, user)


@router.get("/quotes/{quote_id}", response_model=QuoteOut)
async def get_quote(quote_id: uuid.UUID, db: DbSession, user: CurrentUser) -> QuoteOut:
    try:
        return await service.get(db, user, quote_id)
    except ERRORS as exc:
        raise _http(exc) from exc


@router.delete("/quotes/{quote_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove(quote_id: uuid.UUID, db: DbSession, user: CurrentUser) -> None:
    try:
        await service.remove(db, user, quote_id)
    except ERRORS as exc:
        raise _http(exc) from exc
