import pytest
from pydantic import ValidationError

from whitespace_shared.gold import MarketOpportunity


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "exporter": "PAK",
        "market": "DEU",
        "hs6": "630231",
        "data_year": 2024,
        "market_imports_usd": 120_000_000.0,
        "import_growth_3y": 0.15,
        "top_rival": "CHN",
        "top_rival_share_change": -0.09,
        "exporter_share": 0.03,
        "exporter_rca": 12.4,
        "score": 0.81,
        "rank": 1,
        "data_version": "2026-11-15",
    }
    row.update(overrides)
    return row


def test_valid_row() -> None:
    assert MarketOpportunity(**_row()).market == "DEU"  # type: ignore[arg-type]


def test_baci_grouping_codes_accepted() -> None:
    assert MarketOpportunity(**_row(market="S19")).market == "S19"  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field,value",
    [("hs6", "6302"), ("exporter", "pk"), ("exporter_share", 1.5), ("rank", 0)],
)
def test_invalid_rows_rejected(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        MarketOpportunity(**_row(**{field: value}))  # type: ignore[arg-type]
