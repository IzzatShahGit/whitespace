import re

from whitespace_shared.niches import BY_SLUG, NICHES, SECTORS


def test_slugs_unique_and_url_safe() -> None:
    assert len(BY_SLUG) == len(NICHES)
    assert all(re.fullmatch(r"[a-z0-9-]+", n.slug) for n in NICHES)


def test_prefixes_are_valid_hs_digits() -> None:
    for niche in NICHES:
        assert niche.prefixes, niche.slug
        assert all(re.fullmatch(r"\d{2}|\d{4}|\d{6}", p) for p in niche.prefixes), niche.slug


def test_every_niche_belongs_to_a_known_sector() -> None:
    assert {n.sector for n in NICHES} == set(SECTORS)


def test_matching() -> None:
    assert BY_SLUG["socks"].matches("611595")
    assert BY_SLUG["plastic-raw"].matches("390110")
    assert not BY_SLUG["plastic-raw"].matches("392310")  # that's packaging
    assert BY_SLUG["plastic-products"].matches("392310")
