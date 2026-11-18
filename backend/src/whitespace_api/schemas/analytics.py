"""First-party usage analytics: what the client may report, and the admin summary."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

# Actions only the browser sees. Everything else is counted from the database.
ClientEvent = Literal[
    "page_view",
    "deal_sheet_print",
    "deal_sheet_copy_link",
    "email_draft_open",
    "intro_copy",
]


class EventIn(BaseModel):
    event: ClientEvent
    path: str | None = Field(default=None, max_length=500)


class DayStats(BaseModel):
    day: date
    page_views: int
    visitors: int
    sign_ups: int


class Count(BaseModel):
    name: str
    count: int


class Totals(BaseModel):
    users: int
    active_7d: int = Field(description="Signed in during the last 7 days")
    sign_ups: int
    visitors: int
    page_views: int


class AdminStats(BaseModel):
    since: date
    until: date
    totals: Totals = Field(description="Over the period, except users and active_7d")
    days: list[DayStats]
    top_pages: list[Count]
    actions: list[Count] = Field(description="Feature use over the period")
