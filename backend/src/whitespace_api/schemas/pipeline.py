"""The outreach pipeline: companies a user is contacting, by stage."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from whitespace_api.schemas.lead import CompanyKind, LeadSide
from whitespace_shared.gold import COUNTRY_CODE_PATTERN, HS6_PATTERN

Stage = Literal["to_contact", "emailed", "replied", "samples", "negotiating", "won", "lost"]
ACTIVE: tuple[Stage, ...] = ("to_contact", "emailed", "replied", "samples", "negotiating")


def _web(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    value = value.strip()
    if not value.startswith(("http://", "https://")):
        raise ValueError("must start with http:// or https://")
    return value


class ContactIn(BaseModel):
    hs6: str = Field(pattern=HS6_PATTERN)
    market: str = Field(pattern=COUNTRY_CODE_PATTERN)
    side: LeadSide = "buyers"
    name: str = Field(min_length=2, max_length=160)
    kind: CompanyKind | None = None
    city: str | None = Field(default=None, max_length=80)
    website: str | None = Field(default=None, max_length=255)
    source_url: str | None = Field(default=None, max_length=1000)

    _check_web = field_validator("website", "source_url")(_web)


class ContactPatch(BaseModel):
    version: int = Field(ge=1, description="The version you last saw; stale edits get 409")
    stage: Stage | None = None
    note: str | None = Field(default=None, max_length=2000)
    follow_up_on: date | None = Field(default=None, description="Send null to clear it")


class ContactOut(BaseModel):
    id: uuid.UUID
    hs6: str
    product_name: str
    market: str
    market_name: str
    side: LeadSide
    name: str
    kind: str | None
    city: str | None
    website: str | None
    source_url: str | None
    stage: Stage
    note: str | None
    follow_up_on: date | None
    due: bool = Field(description="A follow-up is due today or overdue")
    last_contacted_at: datetime | None
    emails: int = Field(default=0, description="Emails in the conversation")
    reply_waiting: bool = Field(default=False, description="They wrote last: your turn")
    check_verdict: Literal["green", "amber", "red"] | None = Field(
        default=None, description="The latest buyer check, if any"
    )
    version: int
    created_at: datetime
    updated_at: datetime


class ContactAdded(BaseModel):
    contact: ContactOut
    created: bool = Field(description="False if it was already in your pipeline")


class EventOut(BaseModel):
    kind: str
    detail: str
    created_at: datetime


class PipelineSummary(BaseModel):
    total: int
    by_stage: dict[str, int]
    due: list[ContactOut] = Field(description="Follow-ups due today or overdue, oldest first")
