from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from whitespace_api.schemas.trade import CountryOut, DataWindow, MarketItem, ProductOut
from whitespace_shared.gold import CountryCode, HS6Code

Role = Literal["exporter", "consultant", "agency", "other"]
Goal = Literal["sell", "buy", "both"]

MAX_PRODUCTS = 5
MAX_CURRENT_MARKETS = 60


class ProfileIn(BaseModel):
    exporter: CountryCode = Field(description="The user's country (exports from / buys into)")
    role: Role
    goal: Goal = "sell"
    products: Annotated[list[HS6Code], Field(min_length=1, max_length=MAX_PRODUCTS)]
    current_markets: Annotated[list[CountryCode], Field(max_length=MAX_CURRENT_MARKETS)] = []


class ProfileOut(BaseModel):
    exporter: CountryOut
    role: Role
    goal: Goal
    products: list[ProductOut]
    current_markets: list[CountryOut]
    updated_at: datetime


class ProductOpportunities(BaseModel):
    product: ProductOut
    total_markets: int = Field(description="All ranked markets for this product")
    top: list[MarketItem] = Field(description="Best new markets (excluding current ones)")


class BestMove(BaseModel):
    product: ProductOut
    market: MarketItem


class Dashboard(BaseModel):
    profile: ProfileOut
    data: DataWindow | None
    best_moves: list[BestMove] = Field(
        description="Top actionable markets across all products (verdict: go or test)"
    )
    products: list[ProductOpportunities]


class RangeIdea(BaseModel):
    """A product the user could add: same customs family, already exported competitively."""

    product: ProductOut
    same_family: bool = Field(description="Same 4-digit heading as one of the user's products")
    markets: int = Field(description="Ranked markets for it")
    strong_markets: int = Field(description="Markets with a strong opportunity score")
    top: MarketItem = Field(description="Its best market")


class GrowRange(BaseModel):
    ideas: list[RangeIdea]
