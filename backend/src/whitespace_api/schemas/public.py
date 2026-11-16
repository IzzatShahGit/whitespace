from __future__ import annotations

from pydantic import BaseModel

from whitespace_api.schemas.trade import Action, CountryOut, ProductOut, Tone


class PreviewMarket(BaseModel):
    market: CountryOut
    action: Action
    headline: str
    tone: Tone
    imports_usd: float
    growth: float


class Preview(BaseModel):
    """A taste of the product for signed-out visitors: the top markets for one product."""

    exporter: CountryOut
    product: ProductOut
    total: int
    markets: list[PreviewMarket]
    data_year: int | None
