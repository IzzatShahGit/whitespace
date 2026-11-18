"""Market requirements: what a shipment needs to enter a market, each item sourced."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["document", "certificate", "product_rule", "labelling", "registration", "other"]
Need = Literal["required", "often_asked", "depends"]
Status = Literal["missing", "pending", "ready", "failed"]


class RequirementSource(BaseModel):
    id: str = Field(description="S1, S2, ...")
    title: str
    url: str
    domain: str
    official: bool = Field(description="A government or intergovernmental site")


class Requirement(BaseModel):
    key: str = Field(description="Stable id for ticking it off")
    category: Category
    title: str
    detail: str
    need: Need
    issuer: str | None = Field(description="Who issues it or checks it, if the page says")
    quote: str = Field(description="The words on the source page that back this item")
    source: str


class RequirementsContent(BaseModel):
    items: list[Requirement]
    sources: list[RequirementSource]
    research_available: bool
    removed: int = Field(description="Items dropped because their page didn't back them")


class RequirementsUsage(BaseModel):
    searches: int
    pages_read: int
    input_tokens: int
    output_tokens: int
    models: list[str]


class RequirementsOut(BaseModel):
    status: Status
    content: RequirementsContent | None = None
    error: str | None = None
    generated_at: datetime | None = None
    stale: bool = False
    done: list[str] = Field(default_factory=list, description="Item keys this user ticked")
