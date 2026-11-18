"""Shipping documents for a won deal: commercial invoice, packing list, proof of origin."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from whitespace_api.schemas.quotes import Party, QuoteLine


class ShipmentIn(BaseModel):
    quote_id: uuid.UUID


class ShipmentDetails(BaseModel):
    """What the exporter fills in; everything is optional until they print."""

    invoice_date: date | None = None
    consignee_address: str | None = Field(default=None, max_length=400)
    notify_party: str | None = Field(default=None, max_length=300)
    vessel: str | None = Field(default=None, max_length=80)
    voyage: str | None = Field(default=None, max_length=40)
    bl_number: str | None = Field(default=None, max_length=40)
    containers: str | None = Field(default=None, max_length=200, description="Container numbers")
    seals: str | None = Field(default=None, max_length=200)
    final_destination: str | None = Field(default=None, max_length=120)
    packages: int | None = Field(default=None, ge=1, le=1_000_000)
    package_type: str = Field(default="cartons", max_length=30)
    net_kg: float | None = Field(default=None, gt=0, le=5_000_000)
    gross_kg: float | None = Field(default=None, gt=0, le=5_000_000)
    package_size_cm: str | None = Field(
        default=None, max_length=30, description='Length x width x height, e.g. "60x40x40"'
    )
    marks: str | None = Field(default=None, max_length=300, description="Shipping marks")
    origin_criterion: str | None = Field(
        default=None, max_length=20, description='"P" (wholly obtained) or "W" + HS heading'
    )


class ShipmentPatch(ShipmentDetails):
    version: int = Field(ge=1)


class OriginStatement(BaseModel):
    kind: Literal["eu_gsp_statement", "certificate"]
    text: str | None = Field(description="The statement to print, when we know its wording")
    guidance: list[str]


class ChecklistItem(BaseModel):
    title: str
    status: Literal["ready", "fill_in", "from_others"]
    detail: str


class Shipment(BaseModel):
    id: uuid.UUID
    version: int
    quote_id: uuid.UUID | None
    quote_number: str | None
    invoice_number: str
    hs6: str
    market: str
    description: str
    seller: Party
    buyer: Party
    bank_details: str | None
    incoterm: str
    named_place: str
    origin_port: str
    dest_port: str
    origin_country: str
    quantity_kg: float
    lines: list[QuoteLine]
    total_usd: float
    payment_text: str
    details: ShipmentDetails
    volume_m3: float | None = Field(description="From package size and count")
    origin: OriginStatement
    checklist: list[ChecklistItem]
    warnings: list[str] = Field(description="Missing or inconsistent details, for the seller")
    created_at: datetime
    updated_at: datetime


class ShipmentSummary(BaseModel):
    id: uuid.UUID
    invoice_number: str
    buyer_name: str
    market: str
    total_usd: float
    created_at: datetime
