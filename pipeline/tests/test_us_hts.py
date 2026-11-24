"""US chapter 99 parsing, on text shaped like pypdf's reading of the official schedule."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from whitespace_pipeline.sources import us_hts
from whitespace_shared import us_tariffs

# Rows as pypdf returns them: description, heading (with footnote marker), then columns.
COUNTRY_ROWS = """
Except for products described in headings
9903.05.85-9903.05.92, articles the product of Pakistan, as
provided for in U.S. note 52 to this subchapter.........................
1/9903.05.62
The duty
provided in
the applicable
subheading
The duty provided in
the applicable
subheading + 10%
1/
Except for products described in headings
9903.05.85-9903.05.92 and 9903.05.97, articles the product
of a member state of the European Union, with an ad valorem
rate of duty under column 1 equal to or greater than 10 percent, as provided for.....
1/9903.05.38
No changeThe duty provided in
the applicable
subheading
1/
Except for products described in headings
9903.05.85-9903.05.92 and 9903.05.97, articles the product
of a member state of the European Union, with an ad valorem
rate of duty under column 1 less than 10 percent, as provided for....
1/9903.05.39
No change10%10%1/
Except for products described in headings
9903.05.85-9903.05.92, articles the product of Vietnam, as
provided for in U.S. note 52 to this subchapter.........................
9903.05.84
The duty provided in the applicable subheading + 12.5%
"""

CHINA = """
(a) ... subject to the additional 25 percent ad valorem rate of duty imposed by heading 9903.88.01
(b) Heading 9903.88.01 applies to all products of China that are classified in the following
8-digit subheadings, except products provided for in heading 9903.88.05:
8481.80.108481.80.30
(c) For the purposes of heading 9903.88.02, the additional 25 percent ad valorem rate of duty
imposed by heading 9903.88.02 applies.
(d) Heading 9903.88.02 applies to all products of China that are classified in:
8504.40.95
(e) For the purposes of heading 9903.88.03, the additional 25 percent ad valorem rate of duty
imposed by heading 9903.88.03 applies.
(f) Heading 9903.88.03 applies to all products of China that are classified in:
4202.92.084202.92.15
(g) For the purposes of heading 9903.88.04 ...
(r) the additional 7.5 percent ad valorem rate of duty imposed by heading 9903.88.15 applies.
(s) Heading 9903.88.15 applies to:
(i) all products of China in the following 8-digit subheadings: 6302.60.00
(ii) products of China described in statistical reporting numbers 6307.90.9842, 6307.90.98.44
(t) For the purposes of heading 9903.88.16 ...
"""

EXEMPT = """
(b) As provided in heading 9903.05.86, the duties shall not apply to:
0201.30.500201.30.80
0805.90 whole subheading
(c) As provided in heading 9903.05.87, ...
(e) As provided in heading 9903.05.89, pharmaceutical articles:
3004.90.92
(f) As provided in heading 9903.05.90, ...
"""


def test_codes_split_run_together_lines_and_keep_ten_digit_numbers() -> None:
    text = "0101.90.300101.30.000101.29.00 6307.90.9842, 6307.90.98.44 and 0805.90 x 9903.88.01"
    assert us_hts.codes(text) == [
        "01012900", "01013000", "01019030", "080590", "6307909842", "6307909844",
    ]  # fmt: skip


def test_country_rows_added_and_ceiling() -> None:
    duties = us_hts.country_duties(COUNTRY_ROWS, minimum=1)
    assert duties["PAK"] == [us_hts.CountryDuty("9903.05.62", 10.0, ceiling=False)]
    assert duties["VNM"] == [us_hts.CountryDuty("9903.05.84", 12.5, ceiling=False)]
    # The EU's "already at the ceiling" row adds nothing; the other tops up to 10%.
    assert duties[us_tariffs.EU_CODE] == [us_hts.CountryDuty("9903.05.39", 10.0, ceiling=True)]


def test_too_few_countries_fails_instead_of_writing() -> None:
    with pytest.raises(us_hts.ParseError):
        us_hts.country_duties(COUNTRY_ROWS)  # 3 parsed, about 60 expected


def test_china_lists_and_their_rates() -> None:
    lists = {item["name"]: item for item in us_hts.china_lists(CHINA, minimum=1)}
    assert lists["List 1"]["codes"] == ["84818010", "84818030"]
    assert lists["List 3"] == {
        "name": "List 3", "heading": "9903.88.03", "rate": 25.0,
        "codes": ["42029208", "42029215"],
    }  # fmt: skip
    assert lists["List 4A"]["rate"] == 7.5
    assert lists["List 4A"]["codes"] == ["63026000", "6307909842", "6307909844"]


def test_missing_section_fails() -> None:
    with pytest.raises(us_hts.ParseError):
        us_hts.china_lists(CHINA.replace("(s) Heading 9903.88.15 applies", "(s) gone"), minimum=1)


def test_exempt_tables_and_schedule_lookups() -> None:
    assert us_hts.exempt_codes(EXEMPT) == ["02013050", "02013080", "080590", "30049092"]
    index = us_tariffs.CodeIndex.of(us_hts.exempt_codes(EXEMPT))
    assert index.coverage("080590") == us_tariffs.Coverage(full=True, lines=0)
    assert index.coverage("020130") == us_tariffs.Coverage(full=False, lines=2)
    assert index.coverage("610910") is None


def test_build_reads_the_release_from_page_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = (
        "Harmonized Tariff Schedule of the United States Revision 23 (2026)\n"
        + COUNTRY_ROWS + CHINA + EXEMPT
    )  # fmt: skip
    monkeypatch.setattr(us_hts, "MIN_COUNTRIES", 1)
    monkeypatch.setattr(us_hts, "MIN_CHINA_CODES", 1)
    content = us_hts.build(raw, built=datetime(2026, 11, 24, tzinfo=UTC))
    assert content["release"] == "Revision 23 (2026)" and content["built"] == "2026-11-24"
    schedule = us_tariffs.parse(content)
    assert schedule.country["PAK"][0].rate_pct == 10.0
    assert [c.name for c in schedule.china] == ["List 1", "List 2", "List 3", "List 4A"]


def test_built_file_is_current_and_complete() -> None:
    schedule = us_tariffs.load()
    assert schedule is not None, "run `ws-pipeline us-tariffs`"
    assert len(schedule.country) >= us_hts.MIN_COUNTRIES
    assert sum(len(c.codes.lines) for c in schedule.china) > 1_000
