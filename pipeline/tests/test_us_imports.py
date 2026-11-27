"""US imports reference file: Census rows in, consumer codes with 24 months out."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from whitespace_pipeline.sources import us_imports

HEADER = ["I_COMMODITY", "I_COMMODITY_SDESC", "GEN_VAL_MO", "COMM_LVL", "CTY_CODE", "time"]


def test_parse_reads_codes_values_and_names() -> None:
    rows = [
        HEADER,
        ["630260", "TOILET LINEN ", "1500000", "HS6", "-", "2026-09"],
        ["01", "X", "5", "HS2", "-", "2026-09"],
    ]
    assert us_imports.parse(rows) == {"630260": (1_500_000, "TOILET LINEN")}
    assert us_imports.parse([]) == {}
    with pytest.raises(us_imports.SourceError):
        us_imports.parse([["WRONG"]])


def months(value: dict[str, int]) -> dict[str, dict[str, tuple[int, str]]]:
    out = {}
    for i in range(24):
        month = us_imports._month(2024 * 12 + 9 + i)  # 2024-10 .. 2026-09
        out[month] = {code: (v, f"NAME {code}") for code, v in value.items()}
    return out


def test_build_keeps_consumer_codes_with_enough_trade(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(us_imports, "MIN_ROWS", 1)
    data = months({"630260": 1_000_000, "841810": 9_000_000, "950300": 100_000})
    out = us_imports.build(data, built=datetime(2026, 11, 25, tzinfo=UTC))
    assert (out["first_month"], out["last_month"]) == ("2024-10", "2026-09")
    # Fridges aren't an Amazon category we map; $1.2M a year of toys is too thin.
    assert [r["hs6"] for r in out["rows"]] == ["630260"]
    assert out["rows"][0]["m"] == [1000] * 24  # USD thousands


def test_build_refuses_a_short_or_thin_result() -> None:
    with pytest.raises(us_imports.SourceError, match="expected 24 months"):
        us_imports.build({"2026-09": {}}, built=datetime.now(UTC))
    with pytest.raises(us_imports.SourceError, match="consumer codes kept"):
        us_imports.build(months({"630260": 1_000_000}), built=datetime.now(UTC))
