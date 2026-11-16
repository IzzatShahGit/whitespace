import re

from whitespace_shared.country_codes import ISO_NUMERIC
from whitespace_shared.tariff_schemes import SCHEMES, groups_for, schemes_for


def test_every_scheme_is_documented() -> None:
    for reporter, schemes in SCHEMES.items():
        assert re.fullmatch(r"\d{3}", reporter)
        for scheme in schemes:
            assert re.fullmatch(r"[A-Z]\d{2}", scheme.group)  # WITS group codes, e.g. "B29"
            assert scheme.source.startswith("https://")
            assert scheme.members and scheme.members <= ISO_NUMERIC.keys()


def test_lookup() -> None:
    assert [s.name for s in schemes_for("918", "PAK")] == ["EU GSP+"]
    assert [s.group for s in schemes_for("918", "BGD")] == ["B12"]
    assert schemes_for("918", "CHN") == []  # rivals never get a group preference by default
    assert schemes_for("840", "PAK") == []
    assert groups_for("918") == ["B29", "B12", "B31"]
    assert groups_for("392") == []
