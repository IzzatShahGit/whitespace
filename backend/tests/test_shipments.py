"""Shipping documents: built from a quote, numbered without gaps, origin statement wording,
consistency warnings, safe concurrent edits. Plus the account's interface language."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from httpx import AsyncClient

from tests.test_quotes import BASE, lane, offline  # noqa: F401 - pytest fixtures
from whitespace_api.services import shipments as service


@pytest.fixture
def gsp(monkeypatch: pytest.MonkeyPatch) -> None:
    async def scheme(*_: Any) -> str:
        return "EU GSP+"

    async def eur(_: Any) -> float:
        return 0.9

    monkeypatch.setattr(service, "_scheme", scheme)
    monkeypatch.setattr(service, "_eur_per_usd", eur)


async def issue(user: AsyncClient, **extra: Any) -> dict[str, Any]:
    response = await user.post("/api/v1/quotes", json=BASE | {"incoterm": "CIF"} | extra)
    assert response.status_code == 201, response.text
    return response.json()


async def test_documents_from_a_quote(user: AsyncClient, lane: None, gsp: None) -> None:  # noqa: F811
    await user.put("/api/v1/business", json={"company_name": "Towel Co", "address": "Karachi"})
    quote = await issue(user, buyer_address="Seelbach, Germany")
    made = await user.post("/api/v1/shipments", json={"quote_id": quote["id"]})
    assert made.status_code == 201
    s = made.json()
    year = s["invoice_number"][4:8]
    assert s["invoice_number"] == f"INV-{year}-0001" and s["quote_number"] == quote["number"]
    assert s["total_usd"] == quote["total_usd"] and s["lines"] == quote["lines"]
    assert s["details"]["net_kg"] == 9280 and s["buyer"]["address"] == "Seelbach, Germany"

    # EU GSP: the official wording, with blanks until the REX number and criterion exist.
    origin = s["origin"]
    assert origin["kind"] == "eu_gsp_statement"
    assert origin["text"].startswith("The exporter … of the products covered by this document")
    assert "of Pakistan preferential origin" in origin["text"]
    assert "Generalised System of Preferences of the European Union" in origin["text"]
    assert any("€6,000" in g for g in origin["guidance"])
    # $44k of towels is above €6,000: the REX number is needed.
    assert any("needs your REX number" in w for w in s["warnings"])
    titles = {c["title"]: c["status"] for c in s["checklist"]}
    assert titles["Commercial invoice"] == "ready" and titles["Packing list"] == "fill_in"
    assert titles["Insurance certificate"] == "from_others"  # CIF

    await user.put(
        "/api/v1/business",
        json={"company_name": "Towel Co", "address": "Karachi", "rex_number": "PKREX123"},
    )
    url = f"/api/v1/shipments/{s['id']}"
    filled = await user.patch(
        url,
        json={"version": 1, "packages": 464, "gross_kg": 9650, "package_size_cm": "60x40x40",
              "origin_criterion": "W 63.02", "marks": "HH / SEELBACH / 1-464"},
    )  # fmt: skip
    f = filled.json()
    assert f["version"] == 2 and f["volume_m3"] == pytest.approx(44.54, abs=0.01)
    assert "The exporter PKREX123 of the products" in f["origin"]["text"]
    assert f["origin"]["text"].endswith("origin criterion met is W 63.02.")
    assert not any("REX" in w for w in f["warnings"])
    statuses = {c["title"]: c["status"] for c in f["checklist"]}
    assert statuses["Packing list"] == "ready" and statuses["Statement on origin"] == "ready"


async def test_one_set_per_quote_and_no_number_gaps(
    user: AsyncClient,
    lane: None,  # noqa: F811
    gsp: None,
) -> None:
    first, second = await issue(user), await issue(user)
    clicks = await asyncio.gather(
        *(user.post("/api/v1/shipments", json={"quote_id": first["id"]}) for _ in range(4))
    )
    assert sorted(r.status_code for r in clicks) == [200, 200, 200, 201]
    assert len({r.json()["id"] for r in clicks}) == 1
    other = (await user.post("/api/v1/shipments", json={"quote_id": second["id"]})).json()
    numbers = sorted([clicks[0].json()["invoice_number"], other["invoice_number"]])
    assert [n[-4:] for n in numbers] == ["0001", "0002"]  # no gaps from the double clicks
    assert len((await user.get("/api/v1/shipments")).json()) == 2


async def test_consistency_warnings_and_stale_edits(
    user: AsyncClient,
    lane: None,  # noqa: F811
    gsp: None,
) -> None:
    quote = await issue(user)
    s = (await user.post("/api/v1/shipments", json={"quote_id": quote["id"]})).json()
    url = f"/api/v1/shipments/{s['id']}"
    odd = (await user.patch(url, json={"version": 1, "net_kg": 9000, "gross_kg": 8000})).json()
    assert any("differs from the invoiced quantity" in w for w in odd["warnings"])
    assert any("gross weight is less" in w for w in odd["warnings"])
    assert any("buyer's address" in w for w in odd["warnings"])

    ok, stale = await asyncio.gather(
        user.patch(url, json={"version": 2, "vessel": "MSC Example"}),
        user.patch(url, json={"version": 2, "vessel": "Other"}),
    )
    assert sorted([ok.status_code, stale.status_code]) == [200, 409]
    assert (await user.patch(url, json={"version": 3, "packages": 0})).status_code == 422
    assert (await user.delete(url)).status_code == 204
    assert (await user.get(url)).status_code == 404
    missing = "00000000-0000-0000-0000-000000000000"
    assert (await user.post("/api/v1/shipments", json={"quote_id": missing})).status_code == 404


async def test_other_lanes_get_certificate_guidance(
    user: AsyncClient,
    lane: None,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def no_scheme(*_: Any) -> None:
        return None

    monkeypatch.setattr(service, "_scheme", no_scheme)
    quote = await issue(user)
    s = (await user.post("/api/v1/shipments", json={"quote_id": quote["id"]})).json()
    assert s["origin"]["kind"] == "certificate" and s["origin"]["text"] is None
    assert any("chamber of commerce" in g for g in s["origin"]["guidance"])


def test_volume_needs_three_sizes() -> None:
    details = service.ShipmentDetails(packages=10, package_size_cm="60 x 40 x 40 cm")
    assert service.volume_m3(details) == 0.96
    assert service.volume_m3(service.ShipmentDetails(packages=10, package_size_cm="60x40")) is None


async def test_account_language(user: AsyncClient) -> None:
    assert (await user.get("/api/v1/auth/me")).json()["locale"] is None
    saved = await user.put("/api/v1/auth/me/locale", json={"locale": "ur"})
    assert saved.status_code == 200 and saved.json()["locale"] == "ur"
    assert (await user.put("/api/v1/auth/me/locale", json={"locale": "xx"})).status_code == 422
