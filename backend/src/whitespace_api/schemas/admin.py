"""What the admin pages read: accounts, one account in depth, and visits."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from whitespace_api.schemas.analytics import Count

Segment = Literal["real", "test", "all"]
UserFilter = Literal["any", "active", "inactive", "disabled", "unverified", "no_profile"]
UserSort = Literal["joined", "last_seen", "most_active", "name"]
VisitFilter = Literal["all", "anonymous", "signed_in"]


class UserRow(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    sign_in: Literal["google", "password", "both"]
    email_verified: bool
    is_active: bool = Field(description="False when an admin disabled the account")
    is_test: bool = Field(description="Marked as a demo or test account")
    is_admin: bool
    exporter: str | None = Field(description="Country they trade from (ISO alpha-3)")
    goal: str | None = Field(description="sell | buy | both")
    created_at: datetime
    last_seen_at: datetime | None
    active_days: int = Field(description="Days they used the app, last 30 days")
    feature_uses: int = Field(description="Metered AI actions, last 30 days")
    visits: int = Field(description="Visits, last 30 days")
    engaged_seconds: int = Field(description="Time on the site, last 30 days")
    country: str | None = Field(description="Where their latest visit came from (ISO alpha-2)")
    source: str | None = Field(description="How they first found the site")


class SegmentCounts(BaseModel):
    real: int
    test: int = Field(description="Test, demo and admin accounts")
    disabled: int


class UserList(BaseModel):
    total: int
    page: int
    per_page: int
    counts: SegmentCounts
    users: list[UserRow]


class Named(BaseModel):
    code: str
    name: str


class ProfileInfo(BaseModel):
    exporter: Named
    role: str
    goal: str
    products: list[Named]
    current_markets: list[Named]
    updated_at: datetime


class VisitUser(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    is_test: bool


class VisitPageOut(BaseModel):
    path: str
    at: datetime
    seconds: int


class VisitOut(BaseModel):
    id: uuid.UUID
    started_at: datetime
    last_seen_at: datetime
    country: str | None = Field(description="ISO alpha-2")
    source: str
    referrer: str | None
    utm_campaign: str | None
    landing: str
    device: str
    browser: str
    os: str
    pages: int
    engaged_seconds: int
    live: bool = Field(description="Active in the last 5 minutes")
    user: VisitUser | None
    journey: list[VisitPageOut]


class VisitList(BaseModel):
    total: int
    page: int
    per_page: int
    live_now: int = Field(description="Visits active in the last 5 minutes")
    visits: list[VisitOut]


class AdminActionOut(BaseModel):
    action: str
    admin_email: str
    created_at: datetime


class UserDetail(BaseModel):
    user: UserRow
    locale: str | None
    digest_enabled: bool
    last_login_at: datetime | None
    open_sessions: int
    profile: ProfileInfo | None
    active_days: list[date] = Field(description="Days they used the app, last 90 days")
    feature_use: list[Count] = Field(description="AI actions by feature, last 30 days")
    made: list[Count] = Field(description="What they created, all time")
    pipeline: list[Count] = Field(description="Companies in their pipeline, by stage")
    visits: list[VisitOut] = Field(description="Latest visits, newest first")
    history: list[AdminActionOut] = Field(description="Admin changes to this account")


class UserUpdate(BaseModel):
    is_active: bool | None = None
    is_test: bool | None = None
