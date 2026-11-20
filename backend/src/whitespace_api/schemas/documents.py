"""Checking a buyer's purchase order or letter of credit against your quote."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from whitespace_api.schemas.screening import Finding, Verdict

DocKind = Literal["letter_of_credit", "purchase_order", "other"]
ReadBy = Literal["swift", "ai", "ai_scan"]


class Terms(BaseModel):
    """What the document says, normalised. None where it doesn't say."""

    kind: DocKind
    number: str | None = None
    issued: date | None = None
    buyer: str | None = Field(default=None, description="Applicant / buyer")
    seller: str | None = Field(default=None, description="Beneficiary / seller")
    issuing_bank: str | None = None
    revocable: bool = False
    currency: str | None = None
    amount: float | None = None
    tolerance_pct: float | None = None
    incoterm: str | None = None
    named_place: str | None = None
    port_of_loading: str | None = None
    port_of_discharge: str | None = None
    latest_shipment: date | None = None
    expiry: date | None = None
    presentation_days: int | None = None
    partial_shipments: str | None = None
    transhipment: str | None = None
    payment: str | None = Field(default=None, description="e.g. at sight, 60 days after B/L")
    confirmation: str | None = None
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    goods: str | None = None
    documents: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)


class ReadField(BaseModel):
    label: str
    value: str
    quote: str | None = Field(default=None, description="Where the document says so")


class DocCheckOut(BaseModel):
    verdict: Verdict
    kind: DocKind
    read_by: ReadBy
    fields: list[ReadField] = Field(description="What we read, for you to compare")
    terms: Terms
    findings: list[Finding] = Field(description="Most serious first")
    quote_number: str | None = Field(description="The quote it was compared with")
    removed: int = Field(default=0, description="Values dropped: not found in the document")
    checked_at: datetime
