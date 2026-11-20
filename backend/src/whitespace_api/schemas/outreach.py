"""Emails with a pipeline contact: drafting, logging what was sent, reading replies."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from whitespace_api.schemas.pipeline import ContactOut, Stage

Purpose = Literal["first", "follow_up", "reply"]
Direction = Literal["out", "in"]
DraftedBy = Literal["ai", "template"]
Intent = Literal[
    "interested",
    "question",
    "order",
    "negotiating",
    "not_interested",
    "out_of_office",
    "other",
]
AskKind = Literal[
    "price",
    "moq",
    "samples",
    "catalogue",
    "specification",
    "certification",
    "payment_terms",
    "delivery_time",
    "meeting",
    "other",
]

MAX_EMAIL_CHARS = 10_000
LANGUAGE_PATTERN = r"^[a-z]{2}(-[A-Z]{2})?$"


class LanguageOption(BaseModel):
    code: str
    name: str


class DraftIn(BaseModel):
    purpose: Purpose | None = Field(
        default=None, description="Default: first if nothing was sent, reply if they wrote last"
    )
    language: str | None = Field(
        default=None, pattern=LANGUAGE_PATTERN, description="Default: the market's best"
    )
    quote_id: uuid.UUID | None = Field(
        default=None, description="Quote to refer to. Default: this contact's latest"
    )
    notes: str | None = Field(
        default=None, max_length=600, description="What you want to say, in your own words"
    )


class DraftOut(BaseModel):
    subject: str
    body: str
    language: str
    purpose: Purpose
    drafted_by: DraftedBy
    quote_number: str | None = Field(description="The quote the draft refers to, if any")
    checks: list[str] = Field(
        description="Things to look at before sending: figures not found in your quote or "
        "the conversation, placeholders left to fill"
    )


class SentIn(BaseModel):
    subject: str | None = Field(default=None, max_length=200)
    body: str = Field(min_length=1, max_length=MAX_EMAIL_CHARS)
    language: str | None = Field(default=None, pattern=LANGUAGE_PATTERN)


class ReplyIn(BaseModel):
    text: str = Field(min_length=10, max_length=MAX_EMAIL_CHARS, description="Their email")


class Ask(BaseModel):
    kind: AskKind
    detail: str = Field(description="What they want, in a few words")
    quote: str = Field(description="Their own words, as written in the email")


class RedFlag(BaseModel):
    code: str
    severity: Literal["high", "medium"]
    label: str
    quote: str


class ReplyAnalysis(BaseModel):
    intent: Intent
    summary: str = Field(description="One sentence, in English")
    language: str | None = Field(description="Language the reply is written in")
    asks: list[Ask] = Field(description="Only items whose quote was found in the reply")
    deadline: str | None = Field(description="A date or time limit they set, as written")
    red_flags: list[RedFlag]
    suggested_stage: Stage | None = Field(description="Where this contact now belongs")
    removed: int = Field(default=0, description="Items dropped: not found in the reply")
    read_by: DraftedBy = Field(description="template: the model was unavailable")


class MessageOut(BaseModel):
    id: uuid.UUID
    direction: Direction
    subject: str | None
    body: str
    language: str | None
    analysis: ReplyAnalysis | None
    created_at: datetime


class ThreadOut(BaseModel):
    messages: list[MessageOut] = Field(description="Oldest first")
    languages: list[LanguageOption] = Field(description="For this market, best first")
    next_purpose: Purpose


class MessageSaved(BaseModel):
    message: MessageOut
    contact: ContactOut
