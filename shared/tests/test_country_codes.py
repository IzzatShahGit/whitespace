import re

import pytest

from whitespace_shared.country_codes import COMTRADE_NUMERIC, ISO_ALPHA2, ISO_NUMERIC


@pytest.mark.parametrize(
    "iso3,numeric",
    [
        # UN Comtrade (and BACI) use 842, 251, 699, 757 and 579 for these: never here.
        ("USA", "840"),
        ("FRA", "250"),
        ("IND", "356"),
        ("CHE", "756"),
        ("NOR", "578"),
        # BACI's historic "Fed. Rep. of Germany" (280) must not win over today's code.
        ("DEU", "276"),
        ("PAK", "586"),
        ("AFG", "004"),
        ("SDN", "729"),
    ],
)
def test_iso_numeric_codes(iso3: str, numeric: str) -> None:
    assert ISO_NUMERIC[iso3] == numeric


def test_tables_are_clean() -> None:
    assert all(re.fullmatch(r"[A-Z]{3}", k) for k in ISO_NUMERIC)
    assert all(re.fullmatch(r"\d{3}", v) for v in ISO_NUMERIC.values())
    assert len(set(ISO_NUMERIC.values())) == len(ISO_NUMERIC)  # one code per country
    assert ISO_ALPHA2.keys() == ISO_NUMERIC.keys()
    assert len(set(ISO_ALPHA2.values())) == len(ISO_ALPHA2)
    assert ISO_ALPHA2["NAM"] == "NA"  # Namibia, not a missing value


def test_no_groupings_or_historic_entries() -> None:
    assert not {"S19", "R20", "ZA1", "PUS", "SUN", "DDR", "CSK", "SCG", "ANT"} & ISO_NUMERIC.keys()


def test_comtrade_codes_differ_from_iso() -> None:
    assert all(ISO_NUMERIC[iso3] != code for iso3, code in COMTRADE_NUMERIC.items())
    assert not set(COMTRADE_NUMERIC.values()) & set(ISO_NUMERIC.values())
