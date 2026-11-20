"""Finding a product's HS code from a description or a photo."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from whitespace_api.schemas.trade import ProductOut

Confidence = Literal["high", "medium", "low"]


class HsPick(BaseModel):
    hs6: str
    description: str = Field(description="The official wording")
    name: str = Field(description="Everyday name")
    confidence: Confidence
    why: str


class HsFinderOut(BaseModel):
    query: str = Field(description="The description searched (from the photo, if any)")
    from_photo: bool
    picks: list[HsPick] = Field(description="Best first; empty if nothing fits")
    questions: list[str] = Field(description="Answers that would decide between the picks")
    others: list[ProductOut] = Field(description="Other close products, to browse")
    method: Literal["ai", "search"] = Field(description="search: AI unavailable, closest words")
    semantic: bool = Field(description="False if meaning-based search was unavailable")
