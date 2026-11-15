from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from whitespace_api.schemas.trade import CountryOut, DataWindow, MarketItem, ProductOut
from whitespace_shared.gold import CountryCode, HS6Code

Role = Literal["exporter", "consultant", "agency", "other"]

MAX_PRODUCTS = 5
MAX_CURRENT_MARKETS = 60


class ProfileIn(BaseModel):
    exporter: CountryCode
    role: Role
    products: Annotated[list[HS6Code], Field(min_length=1, max_length=MAX_PRODUCTS)]
    current_markets: Annotated[list[CountryCode], Field(max_length=MAX_CURRENT_MARKETS)] = []


class ProfileOut(BaseModel):
    exporter: CountryOut
    role: Role
    products: list[ProductOut]
    current_markets: list[CountryOut]
    updated_at: datetime


class ProductOpportunities(BaseModel):
    product: ProductOut
    total_markets: int = Field(description="All ranked markets for this product")
    top: list[MarketItem] = Field(description="Best new markets (excluding current ones)")


class Dashboard(BaseModel):
    profile: ProfileOut
    data: DataWindow | None
    products: list[ProductOpportunities]
