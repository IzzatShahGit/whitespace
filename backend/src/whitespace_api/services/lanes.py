"""Trade-lane direction: container rates are not the same both ways.

Ships fill up where more goods are made than bought (East Asia above all) and sail back
part-empty, so the "backhaul" direction is much cheaper: Europe -> China often costs a
third to a half of China -> Europe. Each region gets a container-surplus score; a lane
running against the flow (to a higher score) is discounted, never below `FLOOR`.

The base sea rates are calibrated on headhaul lanes (e.g. Karachi -> Northern Europe).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Direction = Literal["headhaul", "backhaul", "balanced"]

PER_POINT = 0.2  # discount per point of surplus gap
FLOOR = 0.4


def codes(text: str) -> frozenset[str]:
    return frozenset(text.split())


REGIONS: dict[str, tuple[float, frozenset[str]]] = {
    "East Asia": (3.0, codes(
        "CHN HKG MAC TWN KOR JPN VNM THA MYS SGP IDN PHL KHM BRN MMR LAO MNG"
    )),
    "South Asia": (2.0, codes(
        "PAK IND BGD LKA NPL BTN MDV AFG"
    )),
    "Europe": (1.0, codes(
        "DEU NLD BEL LUX FRA GBR IRL ITA ESP PRT GRC POL SWE DNK NOR FIN EST LVA "
        "LTU AUT CHE CZE SVK HUN SVN HRV ROU BGR SRB BIH MNE ALB MKD MLT CYP ISL "
        "UKR BLR MDA RUS TUR GEO ARM AZE"
    )),
    "Central Asia": (1.0, codes(
        "KAZ UZB KGZ TJK TKM"
    )),
    "Latin America": (1.0, codes(
        "MEX BRA ARG CHL PER ECU COL VEN URY PRY BOL PAN CRI GTM HND SLV NIC DOM "
        "JAM CUB TTO GUY SUR BLZ HTI BHS BRB"
    )),
    "Middle East": (0.5, codes(
        "ARE SAU QAT KWT OMN BHR IRN IRQ ISR JOR LBN SYR YEM PSE"
    )),
    "Africa": (0.5, codes(
        "EGY MAR DZA TUN LBY SDN SSD DJI ERI ETH SOM KEN TZA UGA RWA BDI MOZ MWI "
        "ZMB ZWE ZAF NAM BWA LSO SWZ AGO COG COD GAB CMR CAF TCD NGA NER BEN TGO "
        "GHA CIV LBR SLE GIN GNB SEN GMB MLI BFA MRT MDG MUS CPV STP GNQ COM SYC"
    )),
    "Oceania": (0.5, codes(
        "AUS NZL PNG FJI"
    )),
    "North America": (0.0, codes(
        "USA CAN"
    )),
}  # fmt: skip
NEUTRAL = 1.0  # unlisted countries


@dataclass(frozen=True)
class Lane:
    direction: Direction
    factor: float  # multiplies the sea rate
    origin_region: str | None
    dest_region: str | None


def region(country: str) -> tuple[str | None, float]:
    for name, (score, members) in REGIONS.items():
        if country in members:
            return name, score
    return None, NEUTRAL


def lane(origin: str, dest: str) -> Lane:
    origin_region, from_score = region(origin)
    dest_region, to_score = region(dest)
    gap = from_score - to_score
    if gap >= 0:
        direction: Direction = "headhaul" if gap > 0 else "balanced"
        return Lane(direction, 1.0, origin_region, dest_region)
    factor = round(max(FLOOR, 1 + PER_POINT * gap), 2)
    return Lane("backhaul", factor, origin_region, dest_region)
