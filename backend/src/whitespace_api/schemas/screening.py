"""Buyer checks: is this company who it says it is, and is it safe to deal with?"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from whitespace_shared.gold import COUNTRY_CODE_PATTERN

Verdict = Literal["green", "amber", "red"]
Severity = Literal["high", "medium", "ok", "info"]


class CheckIn(BaseModel):
    name: str = Field(min_length=2, max_length=160, description="The company's name")
    country: str = Field(pattern=COUNTRY_CODE_PATTERN)
    website: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=320, description="The address they use")
    vat: str | None = Field(default=None, max_length=20, description="EU VAT number, if given")
    message: str | None = Field(default=None, max_length=10_000, description="Their email")
    contact_id: uuid.UUID | None = Field(
        default=None, description="A pipeline contact: its website and replies are used too"
    )

    @field_validator("website", "email", "vat", "message")
    @classmethod
    def _blank(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @field_validator("email")
    @classmethod
    def _email(cls, value: str | None) -> str | None:
        if value is not None and ("@" not in value or "." not in value.rsplit("@", 1)[-1]):
            raise ValueError("doesn't look like an email address")
        return value


class Finding(BaseModel):
    code: str
    severity: Severity
    title: str
    detail: str
    quote: str | None = Field(default=None, description="The words that raised it")
    url: str | None = Field(default=None, description="Where to see it yourself")


class SanctionHit(BaseModel):
    source: str
    source_label: str
    name: str
    program: str | None
    url: str | None
    grade: Literal["strong", "possible"]
    score: float


class ListInfo(BaseModel):
    source: str
    label: str
    loaded_at: datetime | None
    names: int
    error: str | None


class BuyerCheckOut(BaseModel):
    verdict: Verdict
    findings: list[Finding] = Field(description="Most serious first")
    sanctions: list[SanctionHit]
    lists: list[ListInfo]
    name: str
    country: str
    website_domain: str | None
    email_domain: str | None
    contact_id: uuid.UUID | None
    checked_at: datetime
