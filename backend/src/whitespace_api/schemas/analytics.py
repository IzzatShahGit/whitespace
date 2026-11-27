"""First-party usage analytics: what the client may report, and the admin summary."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

# Actions only the browser sees. Everything else is counted from the database.
ClientEvent = Literal[
    "page_view",
    "engage",  # seconds of engaged time on `path`
    "deal_sheet_print",
    "deal_sheet_copy_link",
    "email_draft_open",
    "intro_copy",
]


class EventIn(BaseModel):
    event: ClientEvent
    path: str | None = Field(default=None, max_length=500)
    # Sent with the first page view of a tab: where the visit came from.
    referrer: str | None = Field(default=None, max_length=500)
    utm_source: str | None = Field(default=None, max_length=100)
    utm_campaign: str | None = Field(default=None, max_length=100)
    seconds: int | None = Field(default=None, ge=0, le=3600)


class DayStats(BaseModel):
    day: date
    page_views: int
    visitors: int
    sign_ups: int = Field(description="Real accounts only")
    active_users: int = Field(description="Real accounts that used the app that day")
    visits: int


class Count(BaseModel):
    name: str
    count: int


class Totals(BaseModel):
    users: int = Field(description="Real accounts (not test, demo or admin)")
    test_users: int = Field(description="Test, demo and admin accounts")
    active_7d: int = Field(description="Real accounts that used the app in the last 7 days")
    active_30d: int
    sign_ups: int
    visitors: int
    page_views: int


class VisitSummary(BaseModel):
    """Visits over the period, leaving out visits by test, demo and admin accounts."""

    live_now: int = Field(description="Visits active in the last 5 minutes")
    visits: int
    signed_in: int = Field(description="Visits by someone signed in")
    avg_seconds: int = Field(description="Engaged time per visit")
    avg_pages: float
    bounce_rate: float = Field(description="Share of visits with one page and under 10 s")
    countries: list[Count] = Field(description="ISO alpha-2 codes; '' when unknown")
    sources: list[Count]
    devices: list[Count]
    browsers: list[Count]
    landing: list[Count]


class AdminStats(BaseModel):
    since: date
    until: date
    totals: Totals = Field(description="Over the period, except users and active counts")
    days: list[DayStats]
    top_pages: list[Count]
    actions: list[Count] = Field(description="Feature use over the period")
    visits: VisitSummary
