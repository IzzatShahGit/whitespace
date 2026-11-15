import re

import pytest

from whitespace_shared.aliases import ALIASES, codes_for, match_aliases, words


def test_codes_are_valid_hs_digits() -> None:
    for alias, codes in ALIASES.items():
        assert codes, alias
        assert all(re.fullmatch(r"\d{2}|\d{4}|\d{6}", c) for c in codes), alias


@pytest.mark.parametrize(
    "query,first",
    [
        ("footballs", "950662"),
        ("Football", "950662"),
        ("cricket balls", "950669"),
        ("cricket ball from sialkot", "950669"),
        ("balls", "950662"),
        ("t-shirts", "6109"),
        ("bed sheets", "630221"),
        ("Basmati rice", "100630"),
        ("ball bearings", "848210"),
        ("pink salt", "250100"),
    ],
)
def test_everyday_words_find_the_right_codes(query: str, first: str) -> None:
    assert codes_for(query)[0] == first


def test_specific_alias_beats_general_one() -> None:
    assert match_aliases("cricket balls") == ["cricket ball"]  # not also "ball" or "cricket"
    assert "ball" not in match_aliases("ball bearings")


def test_no_match_for_unrelated_words() -> None:
    assert codes_for("quantum computers") == []


def test_plural_handling() -> None:
    assert words("Balls, boxes & shoes") == ("ball", "box", "shoe")
    assert words("glass") == ("glass",)  # not "glas"
