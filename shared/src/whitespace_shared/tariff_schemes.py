"""Trade preferences that tariff data records for a group of countries, not per country.

WITS-TRAINS reports many preferential rates under a partner *group* code (e.g. "B29")
instead of each beneficiary's own code, and offers no service that says who is in a
group. This hand-kept table maps our exporter countries to such groups, only where
membership is confirmed twice: by WITS's list of group members (`WITS_GROUPS`) and by
the importing country's official list of beneficiaries today (`Scheme.source`). Anything
unconfirmed is left out, and the duty then falls back to the standard rate, labelled
as such. Left out on purpose: Sri Lanka (EU GSP+ since 2017, but in no group WITS
documents) and India (the EU's standard GSP excludes its textiles).

A group code is a snapshot of membership, so newer years of data may stop using it
while the preference continues (the EU's GSP+ for Pakistan is last recorded under B29,
in 2017). Rates found this way carry their own year.
"""

from __future__ import annotations

from dataclasses import dataclass

# TRAINS preference beneficiaries: group code -> member countries (WITS reference data).
WITS_GROUPS = "https://wits.worldbank.org/data/public/TRAINSPreferenceBenficiaries.xls"


@dataclass(frozen=True)
class Scheme:
    group: str  # WITS-TRAINS partner group code
    name: str  # how sentences name it
    members: frozenset[str]  # our exporters (ISO alpha-3) confirmed in the group
    source: str  # the importing country's official list of beneficiaries


# Keyed by WITS-TRAINS reporter: 918 = European Union, 124 = Canada, 036 = Australia.
SCHEMES: dict[str, tuple[Scheme, ...]] = {
    "918": (
        # WITS B29 "EU Special incentive arrangement: 2017" (8 countries).
        Scheme(
            group="B29",
            name="EU GSP+",
            members=frozenset({"PAK"}),
            source="https://trade.ec.europa.eu/access-to-markets/en/content/generalised-scheme-preferences-plus-gsp",
        ),
        # WITS B12 "GSP for LDC Beneficiaries: 2017" (48 countries); EU GSP Annex IV.
        Scheme(
            group="B12",
            name="EU Everything But Arms",
            members=frozenset({"BGD", "ETH"}),
            source="https://eur-lex.europa.eu/eli/reg/2012/978/oj",
        ),
        # WITS B31 "EU - EPA countries (KEN, CIV) 2017"; Market Access Regulation Annex I.
        Scheme(
            group="B31",
            name="EU Economic Partnership Agreement",
            members=frozenset({"KEN"}),
            source="https://eur-lex.europa.eu/eli/reg/2016/1076/oj",
        ),
    ),
    "124": (
        # WITS B13 "GSP for LDC Beneficiaries: Canada 2017" (49 countries).
        Scheme(
            group="B13",
            name="Canada's Least Developed Country Tariff",
            members=frozenset({"BGD", "ETH"}),
            source="https://www.cbsa-asfc.gc.ca/trade-commerce/tariff-tarif/2025/01-99/countries-pays-eng.pdf",
        ),
    ),
    "036": (
        # WITS L71 "GSP for LDC: Australia 2006" (50 countries); Schedule 1, Part 2.
        Scheme(
            group="L71",
            name="Australia's least developed country preference",
            members=frozenset({"BGD", "ETH"}),
            source="https://www.abf.gov.au/importing-exporting-and-manufacturing/tariff-classification/current-tariff/schedule-1",
        ),
    ),
}


def schemes_for(reporter: str, exporter: str) -> list[Scheme]:
    """The confirmed schemes `exporter` belongs to in this tariff area."""
    return [s for s in SCHEMES.get(reporter, ()) if exporter in s.members]


def groups_for(reporter: str) -> list[str]:
    """Group codes to fetch for this tariff area, so any listed exporter is covered."""
    return [s.group for s in SCHEMES.get(reporter, ())]
