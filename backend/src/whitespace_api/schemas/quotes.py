"""Quotes and proforma invoices: what the exporter enters, what the buyer receives."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from whitespace_api.schemas.freight import ContainerKind
from whitespace_shared.gold import COUNTRY_CODE_PATTERN, HS6_PATTERN

Incoterm = Literal["FOB", "CFR", "CIF", "DAP"]
PaymentTerms = Literal["advance", "deposit_30", "lc_sight", "cad", "open_30"]
QuoteKind = Literal["quote", "proforma"]


class BusinessIn(BaseModel):
    company_name: str | None = Field(default=None, max_length=160)
    address: str | None = Field(default=None, max_length=400)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=320)
    website: str | None = Field(default=None, max_length=255)
    tax_id: str | None = Field(default=None, max_length=60, description="NTN / VAT / EORI")
    bank_details: str | None = Field(default=None, max_length=600)


class BusinessOut(BusinessIn):
    complete: bool = Field(description="Has a company name and an address")


class QuoteIn(BaseModel):
    kind: QuoteKind = "quote"
    hs6: str = Field(pattern=HS6_PATTERN)
    market: str = Field(pattern=COUNTRY_CODE_PATTERN)
    exporter: str | None = Field(
        default=None, pattern=COUNTRY_CODE_PATTERN, description="Default: your profile"
    )
    contact_id: uuid.UUID | None = None
    buyer_name: str = Field(min_length=2, max_length=160)
    buyer_address: str | None = Field(default=None, max_length=400)
    description: str | None = Field(default=None, max_length=300)
    quantity_kg: float = Field(gt=0, le=5_000_000)
    unit_price_fob: float = Field(gt=0, le=10_000, description="USD per kg, FOB")
    incoterm: Incoterm = "FOB"
    container: ContainerKind = "40ft"
    freight_usd: float | None = Field(
        default=None, ge=0, le=1_000_000, description="A forwarder's figure for all the freight"
    )
    payment_terms: PaymentTerms = "deposit_30"
    validity_days: int = Field(default=30, ge=1, le=180)
    notes: str | None = Field(default=None, max_length=1000)


class QuoteLine(BaseModel):
    label: str
    detail: str | None = None
    amount_usd: float


class Party(BaseModel):
    name: str
    address: str | None = None
    country: str
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    tax_id: str | None = None


class Payment(BaseModel):
    key: PaymentTerms
    label: str
    text: str = Field(description="As printed on the quote")
    risk: Literal["low", "medium", "high"] = Field(description="For the seller")
    explain: str = Field(description="For the seller only: what it means for them")


class QuoteOut(BaseModel):
    id: uuid.UUID | None = Field(description="None for a preview")
    number: str | None
    kind: QuoteKind
    issued: date
    valid_until: date
    seller: Party
    buyer: Party
    bank_details: str | None
    hs6: str
    description: str
    market: str
    incoterm: Incoterm
    named_place: str = Field(description="e.g. Karachi (FOB) or Bremerhaven (CIF)")
    origin_port: str
    dest_port: str
    quantity_kg: float
    containers: int
    container: ContainerKind
    unit_price_fob: float
    lines: list[QuoteLine]
    total_usd: float
    unit_price_usd_kg: float = Field(description="Total / quantity, at the chosen incoterm")
    payment: Payment
    terms: list[str] = Field(description="Printed conditions")
    freight_basis: Literal["estimate", "your figure", "none"]
    seller_notes: list[str] = Field(description="For the seller only, never printed")
    contact_id: uuid.UUID | None
    created_at: datetime | None


class QuoteSummary(BaseModel):
    id: uuid.UUID
    number: str
    kind: QuoteKind
    buyer_name: str
    market: str
    hs6: str
    total_usd: float
    created_at: datetime
