"""The Whitespace guide: conversations, and the data cards shown inside replies.

Cards are built from tool results in code, never written by the model, so every
figure on a card is exactly what the data says.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from whitespace_api.schemas.landed_cost import DutyRate, RivalDuty
from whitespace_api.schemas.sourcing import SourcingPick
from whitespace_api.schemas.trade import Action, CountryOut, ProductOut, Tone, Verdict

MAX_MESSAGE_CHARS = 1500


class CardMarket(BaseModel):
    market: CountryOut
    rank: int
    action: Action
    headline: str
    tone: Tone
    imports_usd: float
    growth: float
    already_selling: bool


class MarketsCard(BaseModel):
    type: Literal["markets"] = "markets"
    product: ProductOut
    exporter: CountryOut
    total: int
    items: list[CardMarket]


class MarketCard(BaseModel):
    type: Literal["market"] = "market"
    product: ProductOut
    exporter: CountryOut
    market: CountryOut
    verdict: Verdict
    imports_usd: float
    growth: float
    exporter_share: float
    price_usd_kg: float | None


class SourcingCard(BaseModel):
    type: Literal["sourcing"] = "sourcing"
    product: ProductOut
    buyer: CountryOut
    picks: list[SourcingPick]
    median_price_usd_kg: float | None


class PriceCard(BaseModel):
    type: Literal["price"] = "price"
    product: ProductOut
    market: CountryOut
    currency: str
    stock_value: float
    value_usd: float
    quantity_kg: float | None
    cost_usd_kg: float | None
    market_price_usd_kg: float | None
    revenue_usd: float | None
    tone: Tone | None
    verdict: str | None


class TrendCard(BaseModel):
    type: Literal["trend"] = "trend"
    product: ProductOut
    market: CountryOut
    source: str
    latest_month: str
    change_12m: float | None
    exporter_share_recent: float
    exporter_share_before: float | None


class NewsItem(BaseModel):
    title: str
    url: str
    domain: str
    published: str | None


class NewsCard(BaseModel):
    type: Literal["news"] = "news"
    query: str
    items: list[NewsItem]


class MoneyCard(BaseModel):
    type: Literal["money"] = "money"
    amount: float
    from_currency: str
    to_currency: str
    result: float


class DutyCard(BaseModel):
    type: Literal["duty"] = "duty"
    product: ProductOut
    exporter: CountryOut
    market: CountryOut
    yours: DutyRate
    standard_pct: float
    rivals: list[RivalDuty]
    advantage_pts: float | None = Field(description="vs the main rival (positive: you pay less)")
    summary: str
    source_url: str


Card = Annotated[
    MarketsCard
    | MarketCard
    | SourcingCard
    | PriceCard
    | TrendCard
    | NewsCard
    | MoneyCard
    | DutyCard,
    Field(discriminator="type"),
]


class ChatMessageOut(BaseModel):
    id: uuid.UUID
    role: Literal["user", "assistant"]
    status: Literal["pending", "done", "failed"]
    content: str
    cards: list[Card]
    follow_ups: list[str]
    grounded: bool | None
    created_at: datetime


class ChatThreadOut(BaseModel):
    id: uuid.UUID
    title: str
    updated_at: datetime


class ChatThreadDetail(ChatThreadOut):
    messages: list[ChatMessageOut]


class ChatMessageIn(BaseModel):
    thread_id: uuid.UUID | None = Field(default=None, description="Omit to start a new thread")
    text: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_CHARS)
    ]


class ChatSuggestions(BaseModel):
    prompts: list[str] = Field(description="Starter questions, personalised from the profile")
    remaining_today: int


class ChatEvent(BaseModel):
    """One server-sent event while a reply is produced (documented for clients)."""

    event: Literal["thread", "status", "card", "answer", "error", "done"]
    thread_id: uuid.UUID | None = None
    message_id: uuid.UUID | None = None
    text: str | None = None
    card: Card | None = None
    follow_ups: list[str] | None = None
    grounded: bool | None = None
