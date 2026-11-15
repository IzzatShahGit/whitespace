import pytest

from whitespace_api.services.explain import Facts, label, money, reasons


def facts(**overrides: object) -> Facts:
    base: dict[str, object] = {
        "exporter_name": "Pakistan",
        "rival_name": "China",
        "start_year": 2021,
        "end_year": 2024,
        "market_imports_usd": 164e6,
        "import_growth_3y": 0.19,
        "top_rival_share_change": -0.09,
        "exporter_share": 0.002,
    }
    base.update(overrides)
    return Facts(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "score,expected", [(0.85, "Strong"), (0.70, "Strong"), (0.6, "Good"), (0.2, "Watch")]
)
def test_labels(score: float, expected: str) -> None:
    assert label(score) == expected


@pytest.mark.parametrize(
    "usd,text", [(2.04e9, "$2.0B"), (164e6, "$164M"), (5.5e6, "$5.5M"), (850e3, "$850K")]
)
def test_money(usd: float, text: str) -> None:
    assert money(usd) == text


def test_three_reasons_from_the_numbers() -> None:
    assert reasons(facts()) == [
        "Imports grew 19% a year from 2021 to 2024",
        "China's share fell 9 points since 2021",
        "Pakistan holds under 1% of this market: room to grow",
    ]


def test_falling_demand_and_rising_rival() -> None:
    lines = reasons(facts(import_growth_3y=-0.03, top_rival_share_change=0.04, exporter_share=0.37))
    assert lines == [
        "Imports fell 3% a year from 2021 to 2024",
        "China gained 4 points of share since 2021",
        "Pakistan already holds 37% of this market",
    ]


def test_steady_values_and_no_rival() -> None:
    lines = reasons(
        facts(
            import_growth_3y=0.001,
            rival_name=None,
            top_rival_share_change=None,
            exporter_share=0.05,
        )
    )
    assert lines == [
        "Imports held steady from 2021 to 2024",
        "A $164M market in 2024",
        "Pakistan holds 5% of this market: room to grow",
    ]
