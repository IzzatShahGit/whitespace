"""Company leads found on the web: who to contact to sell into, or buy from, a country.

Every company and event cites the source page it was found on, and its name was checked
(in code) to appear on that page. Only company-level details are kept: no people.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

LeadSide = Literal["buyers", "suppliers"]
LeadStatus = Literal["missing", "pending", "ready", "failed"]
CompanyKind = Literal[
    "importer",
    "distributor",
    "wholesaler",
    "retailer",
    "brand",
    "manufacturer",
    "exporter",
    "agent",
    "other",
]


class LeadSource(BaseModel):
    id: str = Field(description="S1, S2, ...")
    title: str
    url: str
    domain: str


class Lead(BaseModel):
    name: str
    city: str | None = None
    kind: CompanyKind
    handles: str = Field(description="What they deal in, in a few words")
    website: str | None = Field(default=None, description="Only when seen on the source page")
    source: str = Field(description="The source id this company was found on")


class LeadEvent(BaseModel):
    name: str
    city: str | None = None
    when: str | None = Field(default=None, description="As written on the source, if given")
    source: str


class LeadsContent(BaseModel):
    companies: list[Lead]
    events: list[LeadEvent] = Field(description="Trade fairs where these companies meet")
    sources: list[LeadSource] = Field(description="Every page searched, best first")
    research_available: bool = Field(description="False if web search couldn't run")
    removed: int = Field(description="Names dropped because the cited page didn't show them")


class LeadsUsage(BaseModel):
    searches: int
    pages_read: int
    input_tokens: int
    output_tokens: int
    models: list[str]


class LeadsOut(BaseModel):
    status: LeadStatus
    side: LeadSide
    content: LeadsContent | None = None
    error: str | None = None
    generated_at: datetime | None = None
    stale: bool = False
    usage: LeadsUsage | None = None


class IntroIn(BaseModel):
    hs6: str = Field(pattern=r"^\d{6}$")
    country: str = Field(pattern=r"^[A-Z]{3}$")
    side: LeadSide
    company: str = Field(min_length=1, max_length=120)
    kind: CompanyKind = "other"
    handles: str = Field(default="", max_length=200)
    language: str = Field(default="en", pattern=r"^[a-z]{2}(-[A-Z]{2})?$")


class IntroOut(BaseModel):
    subject: str
    body: str
    drafted_by: Literal["ai", "template"]
    checks: list[str] = Field(
        default_factory=list, description="Figures to verify and placeholders to fill"
    )
