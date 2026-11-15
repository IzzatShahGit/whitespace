"""Opportunity score on a hand-built dataset whose answers can be checked by hand."""

from __future__ import annotations

import math

import polars as pl
import pytest

from whitespace_pipeline.gold.opportunity import compute, compute_suppliers
from whitespace_pipeline.io import validate_against
from whitespace_pipeline.silver.baci import FLOWS_SCHEMA
from whitespace_shared.gold import MarketOpportunity, MarketSupplier

TOWELS = "630260"
OTHER = "999999"  # everything else the world trades, so RCA has a baseline
M = 1_000_000


def flows(rows: list[tuple[int, str, str, str, float]]) -> pl.DataFrame:
    return pl.DataFrame(
        [(y, e, i, p, v, None) for y, e, i, p, v in rows], schema=FLOWS_SCHEMA, orient="row"
    )


def world() -> pl.DataFrame:
    rows: list[tuple[int, str, str, str, float]] = []
    for year, scale in ((2021, 1.0), (2022, 1.2), (2023, 1.5), (2024, 2.0)):
        # Germany: towel imports double over 3 years; China dominant at the start, then slips.
        china_de = 8 * M if year == 2021 else 10 * M
        rows += [
            (year, "CHN", "DEU", TOWELS, china_de),
            (year, "PAK", "DEU", TOWELS, 2 * M * scale if year < 2024 else 10 * M),
            # Poland: Pakistan is the top supplier, India second.
            (year, "PAK", "POL", TOWELS, 9 * M),
            (year, "IND", "POL", TOWELS, 4 * M if year == 2021 else 2 * M),
            # Tiny market: under the $10M floor.
            (year, "PAK", "NOR", TOWELS, 0.5 * M),
            # The rest of world trade: China big, Pakistan and India small.
            (year, "CHN", "USA", OTHER, 500 * M),
            (year, "PAK", "USA", OTHER, 5 * M),
            (year, "IND", "USA", OTHER, 400 * M),
        ]
    return flows(rows)


@pytest.fixture
def gold() -> pl.DataFrame:
    return compute(world(), ["PAK", "IND"], "TEST")


def test_columns_match_shared_contract(gold: pl.DataFrame) -> None:
    validate_against(gold, MarketOpportunity)


def test_suppliers_for_ranked_markets(gold: pl.DataFrame) -> None:
    suppliers = compute_suppliers(world(), gold)
    validate_against(suppliers, MarketSupplier)
    de = suppliers.filter(market="DEU", hs6=TOWELS).sort("value_usd", descending=True)
    # Germany 2024: China 10M and Pakistan 10M of 20M; in 2021 China 8M of 10M.
    assert de["supplier"].to_list() == ["CHN", "PAK"] or de["supplier"].to_list() == ["PAK", "CHN"]
    china = de.filter(supplier="CHN").row(0, named=True)
    assert china["share_start"] == pytest.approx(0.8)
    assert china["share_end"] == pytest.approx(0.5)
    assert "NOR" not in suppliers["market"].to_list()  # not a ranked market


def test_growth_is_compound_annual(gold: pl.DataFrame) -> None:
    de = gold.filter(market="DEU", exporter="PAK").row(0, named=True)
    # Germany: 8M + 2M = 10M in 2021, 10M + 10M = 20M in 2024.
    assert de["import_growth_3y"] == pytest.approx(2 ** (1 / 3) - 1)
    assert de["market_imports_usd"] == pytest.approx(20 * M)
    assert de["exporter_share"] == pytest.approx(0.5)


def test_rival_is_largest_supplier_other_than_exporter(gold: pl.DataFrame) -> None:
    de = gold.filter(market="DEU", exporter="PAK").row(0, named=True)
    assert de["top_rival"] == "CHN"
    # China: 8/10 = 80% in 2021 -> 10/20 = 50% in 2024.
    assert de["top_rival_share_change"] == pytest.approx(-0.3)
    assert de["top_rival_share"] == pytest.approx(0.5)

    pl_ = gold.filter(market="POL", exporter="PAK").row(0, named=True)
    assert pl_["top_rival"] == "IND"  # Pakistan itself is the top supplier, so skip it


def test_filters(gold: pl.DataFrame) -> None:
    assert "NOR" not in gold["market"].to_list()  # under $10M
    # India's towel exports are tiny next to its total trade: towel RCA is
    # (2/402) / (31.5/936.5) = 0.15 < 1, so no towel rows. (Its RCA in the filler
    # product is just above 1, so that row legitimately stays.)
    assert gold.filter(exporter="IND", hs6=TOWELS).is_empty()
    assert gold.filter(exporter="IND", hs6=OTHER)["exporter_rca"][0] == pytest.approx(
        (400 / 402) / (905 / 936.5)
    )
    assert (gold["exporter_rca"] >= 1).all()


def test_scores_and_ranks(gold: pl.DataFrame) -> None:
    pak = gold.filter(exporter="PAK", hs6=TOWELS).sort("rank")
    assert pak["rank"].to_list() == list(range(1, pak.height + 1))
    assert pak["score"].is_sorted(descending=True)
    assert all(0 < s <= 1 for s in pak["score"])
    assert not any(math.isnan(s) for s in pak["score"])


def test_bigger_market_wins_when_other_signals_tie() -> None:
    rows = []
    for year in (2021, 2022, 2023, 2024):
        for market, size in (("BIG", 500 * M), ("SMALL", 12 * M)):
            # Same growth (none), same rival behaviour, same zero share for PAK.
            rows.append((year, "CHN", market, TOWELS, size))
        rows += [(year, "PAK", "USA", TOWELS, 50 * M), (year, "CHN", "USA", OTHER, 900 * M)]
    ranked = compute(flows(rows), ["PAK"], "TEST").filter(hs6=TOWELS).sort("rank")
    assert ranked["market"].to_list()[:2] == ["BIG", "SMALL"]


def test_needs_four_years() -> None:
    short = world().filter(pl.col("year") >= 2023)
    with pytest.raises(ValueError, match="Need years"):
        compute(short, ["PAK"], "TEST")
