from __future__ import annotations

from pydantic import BaseModel, Field


class FxRates(BaseModel):
    """Today's exchange rates against the US dollar (updated daily)."""

    base: str = "USD"
    rates: dict[str, float] = Field(description="Units of each currency per 1 US dollar")
    updated: str = Field(description="When the source last published, as it states it")
    source: str = Field(description="Shown with the rates (the free service asks for credit)")
