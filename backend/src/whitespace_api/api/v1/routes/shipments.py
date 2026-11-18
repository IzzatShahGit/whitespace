"""Shipping documents for won deals: commercial invoice, packing list, proof of origin."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status

from whitespace_api.api.deps import (
    AppSettings,
    CurrentUser,
    DbSession,
    HttpClient,
    get_current_user,
)
from whitespace_api.schemas.shipments import Shipment, ShipmentIn, ShipmentPatch, ShipmentSummary
from whitespace_api.services import shipments as service

router = APIRouter(
    prefix="/shipments", dependencies=[Depends(get_current_user)], tags=["shipments"]
)
ERRORS = (service.NotFoundError, service.ConflictError)


def _http(exc: Exception) -> HTTPException:
    code = status.HTTP_409_CONFLICT if isinstance(exc, service.ConflictError) else 404
    return HTTPException(code, str(exc))


@router.post("", response_model=Shipment)
async def create(
    body: ShipmentIn, response: Response, db: DbSession, http: HttpClient, user: CurrentUser,
    settings: AppSettings,
) -> Shipment:  # fmt: skip
    """Documents for the deal behind a quote (one set per quote; asking again opens it)."""
    try:
        shipment, created = await service.create(db, http, user, body.quote_id, settings)
    except ERRORS as exc:
        raise _http(exc) from exc
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return shipment


@router.get("", response_model=list[ShipmentSummary])
async def list_shipments(db: DbSession, user: CurrentUser) -> list[ShipmentSummary]:
    return await service.list_shipments(db, user)


@router.get("/{shipment_id}", response_model=Shipment)
async def get(
    shipment_id: uuid.UUID, db: DbSession, http: HttpClient, user: CurrentUser
) -> Shipment:
    try:
        return await service.get(db, http, user, shipment_id)
    except ERRORS as exc:
        raise _http(exc) from exc


@router.patch("/{shipment_id}", response_model=Shipment)
async def update(
    shipment_id: uuid.UUID, body: ShipmentPatch, db: DbSession, http: HttpClient,
    user: CurrentUser,
) -> Shipment:  # fmt: skip
    """Fill in shipping details. Send the version you last saw; stale edits get 409."""
    try:
        return await service.update_details(db, http, user, shipment_id, body)
    except ERRORS as exc:
        raise _http(exc) from exc


@router.delete("/{shipment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove(shipment_id: uuid.UUID, db: DbSession, user: CurrentUser) -> None:
    try:
        await service.remove(db, user, shipment_id)
    except ERRORS as exc:
        raise _http(exc) from exc
