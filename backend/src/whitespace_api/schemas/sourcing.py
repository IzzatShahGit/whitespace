"""Buying: where to source a product."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from whitespace_api.schemas.trade import CountryOut, ProductOut, Tone

PickKind = Literal["best_value", "most_established", "rising", "current"]


class SourceSignal(BaseModel):
    tone: Tone
    text: str = Field(description="One measured fact, e.g. '18% below the median price'")


class SupplierOption(BaseModel):
    """One country you could buy from, with the measured facts behind it."""

    country: CountryOut
    rank: int = Field(description="By world exports of this product")
    exports_usd: float
    world_share: float
    exports_growth_3y: float | None
    markets_served: int
    unit_price_usd_kg: float | None
    supplies_you_share: float | None = Field(description="Its share of your imports, if any")
    tags: list[str] = Field(description='e.g. "Lowest price", "Supplies you today"')
    signals: list[SourceSignal]


class SourcingPick(BaseModel):
    kind: PickKind
    title: str
    country: CountryOut
    reason: str = Field(description="Why, in one sentence with figures")


class CurrentSupplier(BaseModel):
    country: CountryOut
    share: float
    unit_price_usd_kg: float | None


class SourcingPage(BaseModel):
    buyer: CountryOut
    product: ProductOut
    data_year: int
    median_price_usd_kg: float | None = Field(description="Across the listed suppliers")
    picks: list[SourcingPick]
    suppliers: list[SupplierOption]
    current_suppliers: list[CurrentSupplier] = Field(description="Who supplies the buyer today")


class SourceProductMatch(ProductOut):
    suppliers: int = Field(description="Supplier countries listed for this product")
