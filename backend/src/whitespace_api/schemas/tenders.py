"""Open public tenders, and checks of a company against public registers."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from whitespace_shared.gold import COUNTRY_CODE_PATTERN


class Tender(BaseModel):
    number: str
    title: str
    buyer: str
    countries: list[str] = Field(description="Buyer countries, ISO alpha-3")
    country_names: list[str]
    published: date | None
    deadline: date | None
    days_left: int | None
    value: float | None
    currency: str | None
    url: str
    match: Literal["category", "keyword"] = Field(
        description="category: the notice's CPV codes fit the product too"
    )
    hs6: str
    product_name: str


class TendersOut(BaseModel):
    tenders: list[Tender]
    fetched_at: datetime | None
    stale: bool = Field(description="TED couldn't be reached; this is the last list")
    products: list[str] = Field(description="Product names searched")


class LeiMatch(BaseModel):
    lei: str
    name: str
    city: str | None
    active: bool
    registration_status: str
    registered_as: str | None
    url: str
    exact: bool = Field(description="Same name as the one you checked")


class CompanyCheck(BaseModel):
    name: str
    country: str
    matches: list[LeiMatch]
    available: bool = Field(description="False if the register couldn't be reached")
    checked_at: datetime


class VatIn(BaseModel):
    country: str = Field(pattern=COUNTRY_CODE_PATTERN, description="An EU member, ISO alpha-3")
    number: str = Field(min_length=4, max_length=20)


class VatCheck(BaseModel):
    country: str
    number: str
    valid: bool
    name: str | None
    address: str | None
    checked_at: datetime
