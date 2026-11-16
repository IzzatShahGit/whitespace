"""Sea routes: port choice per country and the shortest-pair rule."""

from __future__ import annotations

from whitespace_pipeline.gold import routes


def test_every_listed_port_exists() -> None:
    ports = routes.load_ports()
    listed = [code for codes in routes.PORTS.values() for code in codes]
    listed += [code for code, _ in routes.LANDLOCKED.values()]
    assert [code for code in listed if code not in ports] == []


def test_landlocked_and_fallback_gateways() -> None:
    ports, mains = routes.load_ports(), routes.main_ports()
    nepal = routes.gateway("NPL", ports, mains)
    assert nepal is not None and nepal.ports[0].code == "INCCU" and nepal.inland_km == 1000
    fallback = routes.gateway("FRO", ports, mains)  # Faroe Islands: not curated
    assert fallback is None or all(p.code.startswith("FO") for p in fallback.ports)


def test_shortest_pair_picks_the_right_coast() -> None:
    ports, mains = routes.load_ports(), routes.main_ports()
    usa = routes.gateway("USA", ports, mains)
    vietnam = routes.gateway("VNM", ports, mains)
    germany = routes.gateway("DEU", ports, mains)
    assert usa and vietnam and germany
    _, _, from_asia = routes.shortest(vietnam, usa)
    _, _, from_europe = routes.shortest(germany, usa)
    assert from_asia.code in {"USLAX", "USSEA"}
    assert from_europe.code in {"USNYC", "USSAV"}
