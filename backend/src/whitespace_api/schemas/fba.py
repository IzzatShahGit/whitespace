"""Selling on Amazon with FBA: is a product worth importing and listing?"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from whitespace_api.schemas.freight import ContainerKind, CostRange
from whitespace_api.schemas.landed_cost import DutyRate
from whitespace_api.schemas.trade import CountryOut, ProductOut, Tone
from whitespace_api.services.fba_fees import CategoryKey, SizeTier

ShippingChoice = Literal["auto", "lcl", "20ft", "40ft"]
CostGroup = Literal["landed", "amazon", "selling"]


class FbaInput(BaseModel):
    """One product, one source country, sold on Amazon US. Inches, pounds, US dollars."""

    hs6: str = Field(pattern=r"^\d{6}$")
    origin: str = Field(pattern=r"^[A-Z]{3}$", description="Where you buy it (ISO alpha-3)")
    unit_cost_usd: float = Field(gt=0, le=10_000, description="Supplier price per unit, FOB")
    price_usd: float = Field(gt=0, le=10_000, description="Your selling price on Amazon")
    category: CategoryKey = "home_kitchen"
    length_in: float = Field(gt=0, le=120, description="Packed unit, longest side")
    width_in: float = Field(gt=0, le=120)
    height_in: float = Field(gt=0, le=120)
    weight_lb: float = Field(gt=0, le=150, description="Packed unit weight")
    units: int = Field(ge=1, le=100_000, description="Units in your first order")
    monthly_sales: int = Field(ge=1, le=100_000, description="Units you expect to sell a month")
    ad_pct: float = Field(default=10, ge=0, le=60, description="Advertising, % of sales")
    return_pct: float = Field(default=3, ge=0, le=60, description="Returned units, %")
    prep_usd: float = Field(default=0, ge=0, le=100, description="Labels and prep, per unit")
    us_shipment_fees_usd: float = Field(
        default=450,
        ge=0,
        le=20_000,
        description="Customs broker, bond and delivery to Amazon, per shipment",
    )
    shipping: ShippingChoice = "auto"
    freight_per_unit_usd: float | None = Field(
        default=None, ge=0, le=1_000, description="Your forwarder's quote; replaces our estimate"
    )


class FbaCost(BaseModel):
    key: str
    label: str
    group: CostGroup = Field(
        description="landed: to Amazon's door; amazon: Amazon's fees; selling: ads, returns"
    )
    usd: CostRange = Field(description="Per unit sold")
    note: str | None = None


class AmazonSize(BaseModel):
    tier: SizeTier
    label: str
    shipping_weight_lb: float = Field(description="Unit or dimensional weight, as Amazon bills")
    cubic_feet: float


class FbaShipment(BaseModel):
    container: ContainerKind | None = Field(description="None when you gave your own freight")
    containers: int = Field(description="How many boxes of that kind (1 unless very large)")
    label: str
    volume_m3: float
    kg: float
    freight_usd: CostRange = Field(description="Whole shipment, to the US port and delivered")
    import_fees_usd: float = Field(description="US customs processing and harbour fees")
    days_low: int | None
    days_high: int | None
    route: str | None = Field(description='e.g. "PKKHI → USLAX"')
    rates_as_of: str | None


class FbaVerdict(BaseModel):
    tone: Tone
    headline: str
    reasons: list[str]


class FbaEstimate(BaseModel):
    product: ProductOut
    origin: CountryOut
    category: str
    size: AmazonSize
    duty: DutyRate
    duty_stale: bool
    shipment: FbaShipment
    costs: list[FbaCost] = Field(description="Per unit sold, in the order they're paid")
    landed_unit: CostRange = Field(description="Product + freight + duty + import fees + prep")
    amazon_fees_unit: float
    total_cost_unit: CostRange
    profit_unit: CostRange = Field(description="low: with the high costs; high: with the low")
    margin: CostRange = Field(description="Profit / price")
    roi: CostRange = Field(description="Profit / landed cost: what each dollar invested earns")
    break_even_price: float | None = Field(description="Lowest price that covers every cost")
    months_of_stock: float
    monthly_profit: CostRange = Field(description="At your expected sales, after the plan fee")
    first_order_cash: CostRange = Field(
        description="Money out before the first sale: goods, freight, duty, fees, one month's plan"
    )
    payback_months: float | None = Field(description="Typical case; None if it doesn't pay back")
    verdict: FbaVerdict
    notes: list[str]
    duty_source_url: str
    fees_as_of: str
