"""Freight estimate: what it costs to ship one container, door of the port to port."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from whitespace_api.schemas.trade import CountryOut

# "lcl": a share of a container (less than container load), for small orders.
ContainerKind = Literal["20ft", "40ft", "40hc", "lcl"]
Stage = Literal["to_port", "after_arrival"]


class CostRange(BaseModel):
    low: float
    typical: float
    high: float


class FreightRoute(BaseModel):
    origin_port: str
    dest_port: str
    sea_nm: float
    sea_km: float
    origin_inland_km: int = Field(description="Road/rail to the origin port (landlocked)")
    dest_inland_km: int = Field(description="Road/rail from the destination port")
    days_low: int
    days_high: int


class FuelPrice(BaseModel):
    brent_usd: float
    as_of: date | None
    source: str
    factor: float = Field(description="Sea freight multiplier vs the reference fuel price")


class LaneInfo(BaseModel):
    direction: Literal["headhaul", "backhaul", "balanced"] = Field(
        description="backhaul: against the main flow of containers, so cheaper"
    )
    factor: float = Field(description="Sea rate multiplier for this direction")


class CostLine(BaseModel):
    key: str
    label: str
    stage: Stage = Field(description="to_port: up to the market's port (CIF); after: beyond")
    usd: CostRange = Field(description="Per container (per shipment if lcl)")


class FreightEstimate(BaseModel):
    origin: CountryOut
    dest: CountryOut
    route: FreightRoute
    container: ContainerKind
    kg_per_container: float = Field(description="Kg in the box, or in the shipment if lcl")
    volume_m3: float = Field(description="Roughly how much space the load takes")
    kg_basis: str = Field(description="Where the load figure comes from")
    value_usd_kg: float | None = Field(description="Goods value used for insurance")
    value_basis: str | None
    fuel: FuelPrice
    lines: list[CostLine]
    to_port: CostRange = Field(description="Per container, to the market's port (CIF)")
    after_arrival: CostRange = Field(description="Per container, port to buyer")
    total: CostRange
    to_port_usd_kg: CostRange
    total_usd_kg: CostRange
    lane: LaneInfo
    rates_as_of: str = Field(description="Month the base container rates were last set")
    notes: list[str]
