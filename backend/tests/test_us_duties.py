"""US additional duties: how chapter 99 rows combine with the normal rate. Pure."""

from __future__ import annotations

import pytest

from whitespace_api.services import us_duties
from whitespace_shared import us_tariffs

SCHEDULE = us_tariffs.parse(
    {
        "release": "Revision 99 (2026)", "source_url": "https://hts.usitc.gov/",
        "built": "2026-11-24",
        "country": {
            "PAK": [{"heading": "9903.05.62", "rate": 10, "ceiling": False}],
            "CHN": [{"heading": "9903.05.31", "rate": 12.5, "ceiling": False}],
            "CAN": [{"heading": "9903.05.29", "rate": 10, "ceiling": False}],
            "BRA": [
                {"heading": "9903.05.01", "rate": 25, "ceiling": False},
                {"heading": "9903.05.27", "rate": 12.5, "ceiling": False},
            ],
            us_tariffs.EU_CODE: [{"heading": "9903.05.39", "rate": 10, "ceiling": True}],
        },
        "country_exempt": ["080590", "02013050"],
        "china": [
            {"name": "List 3", "heading": "9903.88.03", "rate": 25, "codes": ["42029208"]},
            {"name": "List 4A", "heading": "9903.88.15", "rate": 7.5, "codes": ["4202"]},
        ],
    }
)  # fmt: skip


def run(origin: str, hs6: str, base: float = 5.0, *, free: bool = False) -> us_duties.UsExtras:
    return us_duties.extras(
        SCHEDULE, origin=origin, hs6=hs6, base_pct=base, duty_free_by_agreement=free, us_lines=4
    )


def test_country_duty_adds_to_the_normal_rate() -> None:
    out = run("PAK", "630260")
    assert [(d.heading, d.rate_pct, d.note) for d in out.duties] == [("9903.05.62", 10.0, None)]
    assert out.total_pct == 10.0 and out.notes == []


@pytest.mark.parametrize(("base", "extra"), [(4.0, 6.0), (10.0, 0.0), (12.0, 0.0)])
def test_eu_ceiling_tops_up_only_to_ten_percent(base: float, extra: float) -> None:
    out = run("DEU", "630260", base)
    assert out.total_pct == extra
    if extra:
        assert out.duties[0].note == "Tops the normal duty up to 10%."


def test_fully_exempt_product_pays_no_country_duty() -> None:
    out = run("PAK", "080590")
    assert out.duties == [] and "exempt" in out.notes[0]


def test_partly_exempt_product_is_charged_and_says_so() -> None:
    out = run("PAK", "020130")
    assert out.total_pct == 10.0
    assert out.duties[0].note == "1 US tariff lines under this code are exempt."


def test_usmca_goods_are_exempt_but_other_canadian_goods_are_not() -> None:
    assert run("CAN", "630260", 0.0, free=True).duties == []
    assert run("CAN", "630260", 9.1).total_pct == 10.0


def test_china_takes_the_highest_list_and_stacks_on_the_country_duty() -> None:
    out = run("CHN", "420292")  # List 3 names one line; List 4A the whole heading
    assert [d.heading for d in out.duties] == ["9903.05.31", "9903.88.03"]
    assert out.total_pct == 37.5
    assert out.duties[1].note is not None and out.duties[1].note.startswith("Applies to 1 of 4")
    assert any("exclusion" in n for n in out.notes)


def test_partial_china_list_is_applied_with_a_warning() -> None:
    schedule = us_tariffs.parse(
        {
            "release": "r", "source_url": "u", "built": "2026-11-24",
            "country": {}, "country_exempt": [],
            "china": [
                {"name": "List 3", "heading": "9903.88.03", "rate": 25, "codes": ["42029208"]}
            ],
        }
    )  # fmt: skip
    out = us_duties.extras(
        schedule, origin="CHN", hs6="420292", base_pct=0, duty_free_by_agreement=False, us_lines=4
    )
    assert out.total_pct == 25.0
    assert out.duties[0].note == (
        "Applies to 1 of 4 US tariff lines under this code; check your product's 10-digit HTS code."
    )


def test_two_actions_on_one_country_both_apply() -> None:
    assert run("BRA", "630260").total_pct == 37.5


def test_unlisted_country_pays_nothing_extra_but_section_232_is_flagged() -> None:
    assert run("NPL", "630260").duties == []
    out = run("PAK", "732393")  # steel kitchenware: chapter 73
    assert out.total_pct == 10.0 and "Section 232" in out.notes[-1]
