import pytest

from whitespace_api.services.explain import Facts, label, money, reasons, signals, verdict


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


# ---------- verdicts and signals ----------


@pytest.mark.parametrize(
    "overrides,action",
    [
        # Thailand towels: growing, but China supplies 96% and isn't slipping.
        ({"top_rival_share": 0.96, "top_rival_share_change": 0.0}, "hard"),
        # Kyrgyzstan: growing, rival collapsed, Pakistan absent.
        ({"top_rival_share": 0.10, "top_rival_share_change": -0.81}, "go"),
        # Already strong and the rival is gaining.
        ({"exporter_share": 0.24, "top_rival_share_change": 0.03}, "defend"),
        # Already strong, rival not gaining.
        ({"exporter_share": 0.40, "top_rival_share_change": -0.02}, "grow"),
        # Already strong but the market is shrinking: defend, don't "grow".
        ({"exporter_share": 0.26, "import_growth_3y": -0.17}, "defend"),
        # Shrinking demand beats everything except an established position.
        ({"import_growth_3y": -0.06, "top_rival_share": 0.3}, "care"),
        # Flat demand, no dominance.
        ({"import_growth_3y": 0.0, "top_rival_share": 0.3}, "test"),
        # A dominant rival losing a lot of share is an opening, not a wall.
        ({"top_rival_share": 0.70, "top_rival_share_change": -0.10}, "go"),
    ],
)
def test_verdict_rules(overrides: dict[str, object], action: str) -> None:
    assert verdict(facts(**overrides)).action == action


def test_verdict_summary_quotes_the_numbers() -> None:
    v = verdict(facts(top_rival_share=0.96, top_rival_share_change=0.0))
    assert v.headline == "Hard to break in" and v.tone == "negative"
    assert "China supplies 96% of imports" in v.summary
    assert "China" in v.next_step


def test_signals_cover_four_angles_with_figures() -> None:
    s = signals(facts(top_rival_share=0.3))
    assert [x.kind for x in s] == ["demand", "competition", "position", "size"]
    assert s[0].title == "Fast-growing demand" and "19%" in s[0].detail
    assert s[2].title == "Untapped for Pakistan" and "under 1%" in s[2].detail
    assert s[3].title == "Large market" and "$164M" in s[3].detail


@pytest.mark.parametrize(
    "growth,title",
    [
        (0.10, "Fast-growing demand"),
        (0.03, "Growing demand"),
        (0.0, "Stable demand"),
        (-0.05, "Shrinking demand"),
    ],
)
def test_demand_thresholds(growth: float, title: str) -> None:
    assert signals(facts(import_growth_3y=growth))[0].title == title


def test_zero_share_reads_naturally() -> None:
    assert signals(facts(exporter_share=0.0))[2].detail == "Pakistan doesn't sell here yet"
