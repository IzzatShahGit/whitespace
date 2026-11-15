from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Label = Literal["Strong", "Good", "Watch"]


class CountryOut(BaseModel):
    code: str
    name: str


class ProductOut(BaseModel):
    hs6: str
    description: str


class ProductMatch(ProductOut):
    markets: int = Field(description="Ranked markets available for this exporter")


class MarketItem(BaseModel):
    rank: int
    market: CountryOut
    label: Label
    score: float
    market_imports_usd: float
    import_growth_3y: float
    exporter_share: float
    top_rival: CountryOut | None
    top_rival_share_change: float | None
    reasons: list[str] = Field(description="Three plain-language reasons, from the data")
    already_selling: bool = Field(
        default=False, description="The user said they already sell to this market"
    )


class DataWindow(BaseModel):
    start_year: int
    end_year: int
    version: str


class MarketsPage(BaseModel):
    exporter: CountryOut
    product: ProductOut
    data: DataWindow | None = Field(description="None when there are no ranked markets")
    total: int
    limit: int
    offset: int
    items: list[MarketItem]


class SupplierOut(BaseModel):
    country: CountryOut
    value_usd: float
    share_start: float
    share_end: float


class MarketDetail(BaseModel):
    exporter: CountryOut
    product: ProductOut
    data: DataWindow
    market: MarketItem
    suppliers: list[SupplierOut]


class NicheSummary(BaseModel):
    slug: str
    name: str
    products: int = Field(description="Products in this niche with ranked markets")


class SectorOut(BaseModel):
    name: str
    niches: list[NicheSummary]


class NicheProduct(BaseModel):
    product: ProductOut
    markets: int
    best: MarketItem = Field(description="The top-ranked market for this product")


class NicheDetail(BaseModel):
    slug: str
    name: str
    sector: str
    exporter: CountryOut
    products: list[NicheProduct]


class MonthPoint(BaseModel):
    month: str = Field(description="YYYY-MM")
    total: float = Field(description="Imports from all suppliers")
    exporter: float = Field(description="Imports from the exporter country")


class RecentSupplier(BaseModel):
    name: str
    share_recent: float = Field(description="Share of the last 12 months")
    share_before: float | None = Field(description="Share of the 12 months before")


class RecentMovement(BaseModel):
    """Monthly customs data newer than the annual rankings, for EU and US markets."""

    source: str = Field(description="Human-readable source name")
    currency: str
    latest_month: str
    months: list[MonthPoint] = Field(description="Up to 24 months, oldest first")
    change_12m: float | None = Field(
        description="Last 12 months vs the 12 before (None if fewer than 24 months)"
    )
    exporter_share_recent: float
    exporter_share_before: float | None
    suppliers: list[RecentSupplier] = Field(description="Largest suppliers, last 12 months")
    note: str | None = Field(description="How this source differs from the annual data")
    fetched_at: datetime
    stale: bool = Field(description="True if the source was unreachable and this is older")
