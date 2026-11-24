"""US additional duties on top of the normal (column 1) rate. Pure.

Source: HTS chapter 99, parsed from the official schedule into
`whitespace_shared.us_tariffs` (`ws-pipeline us-tariffs`). Rules, from U.S. note 52 and
note 20 of chapter 99:

- Country duty (Section 301, July 2026): adds a percentage to the normal duty, or for a
  few partners tops it up to a ceiling (EU 10%: a 4% duty pays 6% more; 12% pays none).
  Products in the note 52 annexes are exempt, as are USMCA duty-free goods from Canada
  and Mexico.
- China's Section 301 lists add their rate on top of the country duty.

We know a product at HS6; the US charges at 8 or 10 digits. When a list names only some
of the HS6's lines we still apply it and say so: understating a seller's cost is the
mistake that loses them money. Not modelled, and said so: Section 232 product duties
(they replace the country duty for steel, aluminium, copper, wood, vehicles and chips),
China's time-limited product exclusions, anti-dumping duties.
"""

from __future__ import annotations

from dataclasses import dataclass

from whitespace_api.integrations.monthly_trade import EU_MEMBERS
from whitespace_api.schemas.landed_cost import AdditionalDuty
from whitespace_shared.us_tariffs import EU_CODE, Coverage, Schedule

USMCA = frozenset({"CAN", "MEX"})
# Products that Section 232 duties may cover instead of the country duty: chapters 72-76
# (steel, copper, aluminium articles), wood (4407, 4418, 9401, 9403), vehicles and parts
# (8701-8708), chips (8541-8542). A warning only: coverage is set per HTS line.
SECTION_232_CHAPTERS = frozenset({"72", "73", "74", "76"})
SECTION_232_HEADINGS = frozenset(
    {"4407", "4418", "9401", "9403", "8541", "8542"} | {f"870{d}" for d in range(1, 9)}
)


@dataclass(frozen=True)
class UsExtras:
    duties: list[AdditionalDuty]
    notes: list[str]

    @property
    def total_pct(self) -> float:
        return sum(d.rate_pct for d in self.duties)


def _part(coverage: Coverage, us_lines: int | None) -> str | None:
    """ "Applies to 2 of 5 US tariff lines under this code", when not all of them."""
    if coverage.full:
        return None
    of = f" of {us_lines}" if us_lines and us_lines >= coverage.lines else ""
    return (
        f"Applies to {coverage.lines}{of} US tariff lines under this code; "
        "check your product's 10-digit HTS code."
    )


def _section_232(hs6: str) -> bool:
    return hs6[:2] in SECTION_232_CHAPTERS or hs6[:4] in SECTION_232_HEADINGS


def extras(
    schedule: Schedule,
    *,
    origin: str,
    hs6: str,
    base_pct: float,
    duty_free_by_agreement: bool,
    us_lines: int | None = None,
) -> UsExtras:
    """The additional US duties on `hs6` from `origin`, given its normal duty `base_pct`.

    `duty_free_by_agreement`: the normal duty is a 0% trade-agreement rate (USMCA for
    Canada and Mexico). `us_lines`: US tariff lines under the HS6, for wording only.
    """
    duties: list[AdditionalDuty] = []
    notes: list[str] = []
    rates = schedule.country.get(EU_CODE if origin in EU_MEMBERS else origin, ())
    exempt = schedule.country_exempt.coverage(hs6)
    if rates and exempt and exempt.full:
        notes.append("This product is exempt from the US country duty (HTS chapter 99 annex).")
    elif rates and origin in USMCA and duty_free_by_agreement:
        notes.append("Goods that qualify for USMCA are exempt from the US country duty.")
    else:
        for rate in rates:
            pct = max(0.0, rate.rate_pct - base_pct) if rate.ceiling else rate.rate_pct
            if pct <= 0:
                continue
            note = f"Tops the normal duty up to {rate.rate_pct:g}%." if rate.ceiling else None
            if exempt:
                note = " ".join(
                    filter(
                        None, [note, f"{exempt.lines} US tariff lines under this code are exempt."]
                    )
                )
            duties.append(
                AdditionalDuty(
                    name="Section 301 country duty", heading=rate.heading, rate_pct=pct, note=note
                )
            )
    if origin == "CHN":
        listed = [(c, cov) for c in schedule.china if (cov := c.codes.coverage(hs6))]
        if listed:
            china, coverage = max(listed, key=lambda item: item[0].rate_pct)
            duties.append(
                AdditionalDuty(
                    name=f"Section 301, China {china.name}",
                    heading=china.heading,
                    rate_pct=china.rate_pct,
                    note=_part(coverage, us_lines),
                )
            )
            notes.append("Some Chinese products have a time-limited exclusion from Section 301.")
    if _section_232(hs6):
        notes.append(
            "This product may fall under Section 232 (steel, aluminium, copper, wood, vehicles "
            "or chips): that duty replaces the country duty and is not included."
        )
    return UsExtras(duties=duties, notes=notes)
