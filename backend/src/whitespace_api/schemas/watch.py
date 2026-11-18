"""Watchlists (product-markets a user follows) and the notifications they produce."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from whitespace_api.schemas.trade import CountryOut, ProductOut
from whitespace_shared.gold import CountryCode, HS6Code

MAX_READ_IDS = 100

NotificationKind = Literal[
    "imports_up", "imports_down", "share_up", "share_down", "rival_slipping", "follow_up", "tender"
]


class WatchIn(BaseModel):
    exporter: CountryCode | None = Field(
        default=None, description="Exporter country; defaults to the one in your profile"
    )
    hs6: HS6Code
    market: CountryCode


class WatchOut(BaseModel):
    id: uuid.UUID
    exporter: CountryOut
    product: ProductOut
    market: CountryOut
    alerts_available: bool = Field(
        description="Monthly customs data covers this market (EU members, and the US when "
        "configured), so alerts can be sent"
    )
    created_at: datetime


class WatchStatus(BaseModel):
    """Whether the user watches a product-market, for a watch toggle."""

    watching: bool
    id: uuid.UUID | None = Field(description="The watch, to stop watching it")


class NotificationOut(BaseModel):
    id: uuid.UUID
    kind: NotificationKind
    title: str
    body: str = Field(description="Plain sentences with the figures")
    link: str | None = Field(
        description="In-app path to open, e.g. /app/markets/630260/DEU?exporter=PAK"
    )
    data: dict[str, Any] = Field(description="The figures behind the message, and its tone")
    created_at: datetime
    read_at: datetime | None


class NotificationsPage(BaseModel):
    unread: int = Field(description="All unread notifications, not just the ones listed")
    items: list[NotificationOut] = Field(description="Newest first")


class MarkReadIn(BaseModel):
    """Either the notifications to mark read, or `all: true`."""

    ids: list[uuid.UUID] | None = Field(default=None, min_length=1, max_length=MAX_READ_IDS)
    all: bool = False

    @model_validator(mode="after")
    def _one_target(self) -> MarkReadIn:
        if (self.ids is not None) == self.all:
            raise ValueError("Send either ids or all: true")
        return self


class UnreadCount(BaseModel):
    unread: int
