"""Quotes and proformas: Incoterms pricing, numbering under concurrency, snapshots."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from httpx import AsyncClient

from tests.seed import TOWELS
from tests.test_freight import FUEL, route
from whitespace_api.core.http import http_client
from whitespace_api.main import app
from whitespace_api.services import freight
from whitespace_api.services import quotes as service

BASE: dict[str, Any] = {
    "hs6": TOWELS, "market": "DEU", "exporter": "PAK", "buyer_name": "Holiday Heimtex GmbH",
    "quantity_kg": 9280, "unit_price_fob": 5.0, "container": "40ft",
}  # fmt: skip
SEA_40FT = 450 + 0.24 * 6400  # the route's sea rate at the reference fuel price


@pytest.fixture
def offline(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """A stored Karachi-Bremerhaven route, fixed fuel price, and no outside network (the
    duty lookup fails quietly, as it may in production)."""

    async def fixed(http: object, **_: object) -> Any:
        return FUEL

    monkeypatch.setattr(freight.brent_feed, "latest", fixed)

    down = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    app.dependency_overrides[http_client] = lambda: down
    yield
    app.dependency_overrides.pop(http_client, None)


@pytest.fixture
async def lane(offline: None, db_sessionmaker: Any) -> None:
    async with db_sessionmaker() as db:
        db.add(route())
        await db.commit()


async def preview(user: AsyncClient, **extra: Any) -> dict[str, Any]:
    response = await user.post("/api/v1/quotes/preview", json=BASE | extra)
    assert response.status_code == 200, response.text
    return response.json()


async def test_incoterms_add_up(user: AsyncClient, lane: None) -> None:
    fob = await preview(user)
    assert fob["incoterm"] == "FOB" and fob["named_place"] == "Karachi"
    assert fob["total_usd"] == 46_400 and len(fob["lines"]) == 1  # 9,280 kg x $5
    assert fob["containers"] == 1 and fob["freight_basis"] == "none"

    cfr = await preview(user, incoterm="CFR")
    assert cfr["named_place"] == "Bremerhaven"
    assert cfr["lines"][1]["amount_usd"] == pytest.approx(SEA_40FT, abs=0.01)
    assert cfr["total_usd"] == pytest.approx(46_400 + SEA_40FT, abs=0.01)

    cif = await preview(user, incoterm="CIF")
    insured = (46_400 + SEA_40FT) * 1.1
    assert cif["lines"][2]["amount_usd"] == pytest.approx(insured * 0.003, abs=0.01)
    dap = await preview(user, incoterm="DAP")
    assert dap["lines"][3]["label"] == "Unloading and handling at Bremerhaven"
    assert dap["total_usd"] > cif["total_usd"] > cfr["total_usd"] > fob["total_usd"]
    assert dap["unit_price_usd_kg"] == pytest.approx(dap["total_usd"] / 9280, abs=1e-4)
    assert "Import duties, taxes and customs clearance in Germany" in " ".join(dap["terms"])
    assert any("FOB price must already cover" in n for n in dap["seller_notes"])


async def test_containers_freight_override_and_shared(user: AsyncClient, lane: None) -> None:
    two = await preview(user, incoterm="CFR", quantity_kg=12_000)  # > 9,280 kg per 40ft
    assert two["containers"] == 2
    assert two["lines"][1]["amount_usd"] == pytest.approx(SEA_40FT * 2, abs=0.01)
    assert any("last container is only about 29% full" in n for n in two["seller_notes"])

    own = await preview(user, incoterm="CIF", freight_usd=1500)
    assert own["freight_basis"] == "your figure" and own["lines"][1]["amount_usd"] == 1500

    small = await preview(user, incoterm="CFR", container="lcl", quantity_kg=800)
    assert small["containers"] == 1 and "shared" in small["lines"][1]["detail"]
    assert small["lines"][1]["amount_usd"] < SEA_40FT / 2


async def test_errors(user: AsyncClient, lane: None) -> None:
    no_profile = await user.post("/api/v1/quotes/preview", json=BASE | {"exporter": None})
    assert no_profile.status_code == 422 and "profile" in no_profile.json()["detail"]
    same = await user.post("/api/v1/quotes/preview", json=BASE | {"market": "PAK"})
    assert same.status_code == 422
    no_route = await user.post(
        "/api/v1/quotes/preview", json=BASE | {"market": "USA", "incoterm": "CIF"}
    )
    assert no_route.status_code == 422 and "forwarder" in no_route.json()["detail"]
    fob_anyway = await user.post("/api/v1/quotes/preview", json=BASE | {"market": "USA"})
    assert fob_anyway.status_code == 200
    stranger = await user.post(
        "/api/v1/quotes/preview",
        json=BASE | {"contact_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert stranger.status_code == 404


async def test_numbers_are_unique_under_concurrency(user: AsyncClient, lane: None) -> None:
    made = await asyncio.gather(
        *(user.post("/api/v1/quotes", json=BASE | {"incoterm": "CIF"}) for _ in range(5))
    )
    assert all(r.status_code == 201 for r in made)
    numbers = sorted(r.json()["number"] for r in made)
    year = made[0].json()["issued"][:4]
    assert numbers == [f"Q-{year}-{n:04d}" for n in range(1, 6)]
    proforma = await user.post("/api/v1/quotes", json=BASE | {"kind": "proforma"})
    assert proforma.json()["number"] == f"PI-{year}-0006"
    assert len((await user.get("/api/v1/quotes")).json()) == 6


async def test_issued_quotes_are_snapshots(user: AsyncClient, lane: None) -> None:
    await user.put("/api/v1/business", json={"company_name": "Towel Co", "address": "Karachi"})
    issued = (await user.post("/api/v1/quotes", json=BASE)).json()
    assert issued["seller"]["name"] == "Towel Co"
    await user.put("/api/v1/business", json={"company_name": "Renamed Ltd", "address": "X"})
    again = (await user.get(f"/api/v1/quotes/{issued['id']}")).json()
    assert again["seller"]["name"] == "Towel Co" and again["total_usd"] == issued["total_usd"]
    business = (await user.get("/api/v1/business")).json()
    assert business["company_name"] == "Renamed Ltd" and business["complete"] is True
    assert (await user.delete(f"/api/v1/quotes/{issued['id']}")).status_code == 204
    assert (await user.get(f"/api/v1/quotes/{issued['id']}")).status_code == 404


def test_payment_terms_are_complete() -> None:
    assert set(service.PAYMENTS) == {"advance", "deposit_30", "lc_sight", "cad", "open_30"}
    assert service.PAYMENTS["open_30"].risk == "high"
