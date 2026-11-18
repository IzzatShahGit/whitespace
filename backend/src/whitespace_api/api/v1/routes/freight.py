"""Freight estimates: what one container costs from the exporter's port to the buyer."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from whitespace_api.api.deps import DbSession, HttpClient, get_current_user
from whitespace_api.schemas.freight import ContainerKind, FreightEstimate
from whitespace_api.services import freight as service
from whitespace_shared.gold import COUNTRY_CODE_PATTERN, HS6_PATTERN

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["freight"])

CACHE_SECONDS = 3600


@router.get("/freight", response_model=FreightEstimate)
async def estimate(
    response: Response,
    db: DbSession,
    client: HttpClient,
    origin: Annotated[str, Query(pattern=COUNTRY_CODE_PATTERN, description="Shipping from")],
    dest: Annotated[str, Query(pattern=COUNTRY_CODE_PATTERN, description="Shipping to")],
    hs6: Annotated[str, Query(pattern=HS6_PATTERN)],
    container: ContainerKind = "40ft",
    kg_per_container: Annotated[
        float | None, Query(gt=0, le=30_000, description="Kg per box (per shipment if lcl)")
    ] = None,
    value_usd_kg: Annotated[
        float | None, Query(gt=0, le=10_000, description="Goods value for insurance")
    ] = None,
) -> FreightEstimate:
    """One container's cost by stage (low / typical / high), the route and transit time."""
    try:
        result = await service.estimate(
            db, client, origin=origin, dest=dest, hs6=hs6, container=container,
            kg=kg_per_container, value_usd_kg=value_usd_kg,
        )  # fmt: skip
    except service.NoRouteError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    response.headers["Cache-Control"] = f"private, max-age={CACHE_SECONDS}"
    return result
