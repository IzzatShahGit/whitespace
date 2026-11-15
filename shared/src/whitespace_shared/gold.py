"""Gold-table contracts.

The pipeline writes rows with these shapes into Postgres; the API reads them.
Both sides import from here, so a change that breaks one side fails CI.
Table names live here too, so neither side hard-codes them.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

# ISO 3166-1 alpha-3 country code, e.g. "PAK". BACI also reports three statistical
# groupings with non-ISO codes, kept because dropping them distorts market totals:
# S19 "Other Asia, nes" (mostly Taiwan), ZA1 Southern African Customs Union,
# R20 "Europe EFTA, nes". Hence a letter followed by two letters or digits.
COUNTRY_CODE_PATTERN = r"^[A-Z][A-Z0-9]{2}$"
# Six-digit Harmonized System product code, e.g. "630231"
HS6_PATTERN = r"^\d{6}$"

CountryCode = Annotated[str, Field(min_length=3, max_length=3, pattern=COUNTRY_CODE_PATTERN)]
HS6Code = Annotated[str, Field(min_length=6, max_length=6, pattern=HS6_PATTERN)]

MARKET_OPPORTUNITY_TABLE = "gold_market_opportunity"
MARKET_SUPPLIER_TABLE = "gold_market_supplier"
PRODUCT_TABLE = "ref_product"
COUNTRY_TABLE = "ref_country"


class _Contract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Country(_Contract):
    code: CountryCode
    name: str


class Product(_Contract):
    hs6: HS6Code
    description: str
    hs_revision: str = Field(description='HS edition the code belongs to, e.g. "HS17"')


class MarketOpportunity(_Contract):
    """One ranked market for one exporter country and one product."""

    exporter: CountryCode
    market: CountryCode
    hs6: HS6Code
    data_year: int = Field(description="Last year of trade data the score uses")

    market_imports_usd: float = Field(ge=0)
    import_growth_3y: float = Field(description="Compound annual growth over 3 years")
    top_rival: CountryCode | None = Field(
        default=None, description="Largest supplier other than the exporter at the start"
    )
    top_rival_share_change: float | None = None
    exporter_share: float = Field(ge=0, le=1)
    exporter_rca: float = Field(ge=0)

    score: float = Field(ge=0, le=1)
    rank: int = Field(ge=1)
    data_version: str = Field(description="Pipeline run that produced the row")


class MarketSupplier(_Contract):
    """One of the largest suppliers of a product to a market, and how its share moved."""

    market: CountryCode
    hs6: HS6Code
    supplier: CountryCode
    value_usd: float = Field(ge=0, description="Supplier's sales to the market, last year")
    share_start: float = Field(ge=0, le=1, description="Share of the market, first year")
    share_end: float = Field(ge=0, le=1, description="Share of the market, last year")
