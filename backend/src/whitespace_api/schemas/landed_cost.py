"""Import duties and landed cost: what a market charges on a product from you and from
your rivals, and what the goods cost once delivered."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from whitespace_api.schemas.trade import CountryOut, ProductOut, Tone

DutyKind = Literal["preference", "standard"]


class AdditionalDuty(BaseModel):
    """A duty charged on top of the normal rate (US HTS chapter 99)."""

    name: str = Field(description='e.g. "Section 301 country duty"')
    heading: str = Field(description='The legal heading, e.g. "9903.05.62"')
    rate_pct: float = Field(description="Percent of the customs value, added to the normal rate")
    note: str | None = None


class DutyRate(BaseModel):
    """One country's import duty on the product, and where the figure comes from."""

    country: CountryOut
    rate_pct: float = Field(
        description="Total ad valorem duty, percent of the customs value: normal + additional"
    )
    base_pct: float = Field(description="The normal rate alone (MFN or preference)")
    additional: list[AdditionalDuty] = Field(
        default_factory=list, description="Duties on top of the normal rate (US only for now)"
    )
    kind: DutyKind = Field(
        description='"preference": a trade agreement or scheme; "standard": the MFN rate'
    )
    scheme: str | None = Field(description='The preference, when known, e.g. "EU GSP+"')
    year: int = Field(description="Year the source recorded the rate")
    source: str
    note: str | None = Field(description='Caveats, e.g. "a trade preference may apply"')


class RivalDuty(DutyRate):
    share: float = Field(description="The rival's share of the market's imports, last year")
    advantage_pts: float = Field(
        description="The rival's rate minus yours, in percentage points (positive: you pay less)"
    )


class StandardRate(BaseModel):
    """The MFN rate: what countries without a preference pay."""

    rate_pct: float
    year: int
    source: str


class DutyComparison(BaseModel):
    exporter: CountryOut
    market: CountryOut
    product: ProductOut
    yours: DutyRate
    standard: StandardRate
    rivals: list[RivalDuty] = Field(description="The market's largest other suppliers")
    main_rival: CountryOut | None = Field(description="The largest supplier other than you")
    advantage_pts: float | None = Field(
        description="vs the main rival, in percentage points (positive: you pay less)"
    )
    summary: str = Field(description="One sentence with the figures")
    notes: list[str] = Field(description="What the rates leave out")
    source_url: str = Field(description="Where to check the figures")
    fetched_at: datetime
    stale: bool = Field(description="True if the source was unreachable and this is older")


class LandedLine(BaseModel):
    """Cost per kg delivered to the market: price, freight, then duty."""

    country: CountryOut
    fob_usd_kg: float = Field(
        description="Price at the port of export: your cost, or the rival's average price here"
    )
    freight_usd_kg: float = Field(description="Freight and insurance (0 when not given)")
    duty_pct: float
    duty_usd_kg: float
    landed_usd_kg: float = Field(description="FOB + freight + duty")


class LandedCost(BaseModel):
    duties: DutyComparison
    duty_base: Literal["CIF", "FOB"] = Field(
        description="What the market charges duty on: goods plus freight (CIF) or goods (FOB)"
    )
    freight_pct: float | None = Field(description="As given: percent of the FOB value")
    freight_usd_kg: float | None = Field(description="As given: USD per kg")
    yours: LandedLine | None = Field(description="None without your cost per kg")
    rivals: list[LandedLine] = Field(description="Rivals with a known price into this market")
    market_price_usd_kg: float | None = Field(
        description="What the market paid per kg on average, FOB (value / weight)"
    )
    price_year: int | None = Field(description="Year of the market and rival prices")
    margin: float | None = Field(
        description="Share of the market's average price left after your cost"
    )
    tone: Tone | None
    verdict: str | None = Field(description="Your cost against what the market pays")
    explanation: list[str] = Field(description="Two or three sentences with the figures")
    notes: list[str]
