"""Product ideas for Amazon sellers: what sells now, and what the US imports more of."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from whitespace_api.schemas.trade import CountryOut
from whitespace_api.services.fba_fees import CategoryKey


class AmazonCategoryOut(BaseModel):
    key: str
    label: str
    bestsellers_url: str = Field(description="Amazon's live best-seller page for the category")


class ProductSize(BaseModel):
    length_in: float
    width_in: float
    height_in: float
    weight_lb: float
    packed: bool = Field(description="Amazon listed the packed unit (else the item itself)")


class StartingPoint(BaseModel):
    """Where a small seller would likely buy, from US import records: the biggest US
    supplier we can price shipping from, and its import price."""

    origin: CountryOut
    share: float = Field(description="Its share of US imports of this product")
    price_per_kg_usd: float | None
    unit_cost_usd: float | None = Field(description="Price per kg x the product's weight")


class BestsellerItem(BaseModel):
    rank: int
    name: str
    plain_name: str | None = Field(description='What it is, without brand: "steel tumbler"')
    price_usd: float | None
    list_price_usd: float | None = Field(description="Amazon's crossed-out price, if higher")
    stars: float | None = Field(description="Average rating, out of 5")
    reviews: int | None = Field(description="Number of ratings")
    bought: str | None = Field(description='Amazon\'s own figure, e.g. "10K+ bought in past month"')
    brand: str | None
    size: ProductSize | None
    asin: str | None
    url: str
    hs6: str | None = Field(description="Likely customs code, guessed from the name")
    product_name: str | None = Field(description="Our name for that code")
    fee_category: CategoryKey
    start: StartingPoint | None
    moved: int | None = Field(description="Places up (+) or down (-) since last week")
    is_new: bool = Field(description="Not in this category's top list last week")


class BestsellerList(BaseModel):
    category: AmazonCategoryOut
    items: list[BestsellerItem]


class AmazonBestsellersOut(BaseModel):
    captured_at: datetime
    previous_at: datetime | None = Field(description="The capture movement is measured against")
    source: str
    lists: list[BestsellerList]


class CategoryTrend(BaseModel):
    category: AmazonCategoryOut
    imports_usd: float = Field(description="US imports, last 12 months")
    growth: float | None = Field(description="Last 12 months vs the 12 before (0.1 = +10%)")
    recent_growth: float | None = Field(description="Last 3 months vs the same 3 a year earlier")
    codes: int = Field(description="Customs codes counted in this category")


class RisingProduct(BaseModel):
    hs6: str
    name: str
    category: str = Field(description="Amazon category key")
    fee_category: CategoryKey
    in_catalog: bool = Field(description="We have trade data for it (calculator, suppliers)")
    imports_usd: float
    growth: float
    recent_growth: float | None
    monthly_usd: list[float] = Field(description="US imports per month, oldest first")
    china_extra_pct: float | None = Field(description="Extra US duty if bought from China")
    start: StartingPoint | None


class ImportTrends(BaseModel):
    source: str
    source_url: str
    first_month: str
    last_month: str
    categories: list[CategoryTrend]
    rising: list[RisingProduct]


class IdeasOut(BaseModel):
    categories: list[AmazonCategoryOut]
    amazon: AmazonBestsellersOut | None = Field(description="None until the first capture")
    imports: ImportTrends | None
