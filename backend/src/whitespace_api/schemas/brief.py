"""AI market brief: measured facts (customs data) and reported claims (news), kept apart.

Every point cites the ids it rests on: F* for measured facts, C* for reported claims
(each claim belongs to a source S*). Guidance (entry checks, roadmap) carries no figures.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

BriefStatus = Literal["missing", "pending", "ready", "failed"]


class BriefFact(BaseModel):
    id: str = Field(description="F1, F2, ...")
    label: str
    value: str


class BriefSource(BaseModel):
    id: str = Field(description="S1, S2, ...")
    title: str
    url: str
    domain: str
    published: str | None


class BriefClaim(BaseModel):
    id: str = Field(description="C1, C2, ...")
    text: str
    source: str = Field(description="The source id this claim comes from")


class BriefPoint(BaseModel):
    text: str
    refs: list[str] = Field(description="Fact and claim ids this point rests on")


class BriefStep(BaseModel):
    title: str
    detail: str


class BriefContent(BaseModel):
    headline: str
    why_now: list[BriefPoint] = Field(description="Measured: from customs data")
    drivers: list[BriefPoint] = Field(description="Reported: from cited news")
    risks: list[BriefPoint]
    entry_checks: list[str] = Field(description="Guidance: what to verify before exporting")
    roadmap: list[BriefStep] = Field(description="Guidance: steps to a first shipment")
    facts: list[BriefFact]
    claims: list[BriefClaim]
    sources: list[BriefSource]
    research_available: bool = Field(description="False if web research couldn't run")
    removed_points: int = Field(description="Points dropped by the grounding check")


class BriefUsage(BaseModel):
    calls: int
    input_tokens: int
    output_tokens: int
    models: list[str]


class BriefOut(BaseModel):
    status: BriefStatus
    content: BriefContent | None = None
    error: str | None = None
    generated_at: datetime | None = None
    stale: bool = Field(default=False, description="Older than the refresh window")
    usage: BriefUsage | None = None
