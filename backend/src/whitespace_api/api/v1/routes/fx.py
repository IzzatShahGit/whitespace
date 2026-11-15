"""Exchange rates, so people can work in their own currency."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from whitespace_api.api.deps import HttpClient, get_current_user
from whitespace_api.integrations import fx
from whitespace_api.schemas.fx import FxRates

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["fx"])

CACHE_SECONDS = 3600


@router.get("/fx", response_model=FxRates)
async def exchange_rates(response: Response, client: HttpClient) -> FxRates:
    """Every currency against the US dollar: one small payload, converted in the browser."""
    try:
        rates = await fx.rates(client)
    except fx.FxError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    response.headers["Cache-Control"] = f"private, max-age={CACHE_SECONDS}"
    return FxRates(rates=rates.per_usd, updated=rates.updated, source=fx.SOURCE)
