import pytest

from whitespace_shared.countries import display_name


@pytest.mark.parametrize(
    "code,raw,expected",
    [
        ("DEU", "Fed. Rep. of Germany (...1990)", "Germany"),
        ("USA", "USA", "United States"),
        ("KOR", "Rep. of Korea", "South Korea"),
        ("CAF", "Central African Rep.", "Central African Republic"),
        ("VGB", "Br. Virgin Isds", "British Virgin Islands"),
        ("MNP", "N. Mariana Isds", "Northern Mariana Islands"),
        ("SDN", "Sudan (...2011)", "Sudan"),
        ("BLM", "Saint BarthÃ©lemy", "Saint Barthélemy"),
        ("FRA", "France", "France"),
        ("S19", "Other Asia, nes", "Other Asia (n.e.s.)"),
    ],
)
def test_display_names(code: str, raw: str, expected: str) -> None:
    assert display_name(code, raw) == expected
