"""Onboarding profile and the personal dashboard."""

from __future__ import annotations

from httpx import AsyncClient

from tests.seed import BED_LINEN, THREAD, TOWELS

PROFILE = {
    "exporter": "PAK",
    "role": "exporter",
    "products": [TOWELS, BED_LINEN],
    "current_markets": ["THA"],
}


async def save(user: AsyncClient, **overrides: object):  # type: ignore[no-untyped-def]
    return await user.put("/api/v1/me/profile", json={**PROFILE, **overrides})


async def test_no_profile_until_onboarding(user: AsyncClient) -> None:
    assert (await user.get("/api/v1/me/profile")).status_code == 404
    assert (await user.get("/api/v1/me/dashboard")).status_code == 404


async def test_requires_sign_in(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/me/profile")).status_code == 401
    assert (await client.put("/api/v1/me/profile", json=PROFILE)).status_code == 401


async def test_save_and_read_profile(user: AsyncClient) -> None:
    response = await save(user)
    assert response.status_code == 200
    profile = (await user.get("/api/v1/me/profile")).json()
    assert profile["exporter"] == {"code": "PAK", "name": "Pakistan"}
    assert [p["hs6"] for p in profile["products"]] == [TOWELS, BED_LINEN]  # user's order
    assert profile["current_markets"] == [{"code": "THA", "name": "Thailand"}]


async def test_saving_again_replaces(user: AsyncClient) -> None:
    await save(user)
    await save(user, products=[BED_LINEN], current_markets=[], role="consultant")
    profile = (await user.get("/api/v1/me/profile")).json()
    assert [p["hs6"] for p in profile["products"]] == [BED_LINEN]
    assert profile["current_markets"] == [] and profile["role"] == "consultant"


async def test_duplicates_and_own_country_are_dropped(user: AsyncClient) -> None:
    response = await save(user, products=[TOWELS, TOWELS], current_markets=["THA", "PAK", "THA"])
    assert [p["hs6"] for p in response.json()["products"]] == [TOWELS]
    assert [c["code"] for c in response.json()["current_markets"]] == ["THA"]


async def test_rejects_what_the_data_cannot_support(user: AsyncClient) -> None:
    uncovered = await save(user, exporter="FRA")
    assert uncovered.status_code == 422 and "don't cover" in uncovered.json()["detail"]
    no_markets = await save(user, products=[THREAD])  # exists, but no ranked markets
    assert no_markets.status_code == 422 and THREAD in no_markets.json()["detail"]
    unknown_market = await save(user, current_markets=["XXX"])
    assert unknown_market.status_code == 422


async def test_rejects_malformed_input(user: AsyncClient) -> None:
    assert (await save(user, products=[])).status_code == 422
    assert (await save(user, products=["1", "2", "3", "4", "5", "6"])).status_code == 422
    assert (await save(user, role="hacker")).status_code == 422
    assert (await save(user, exporter="pak")).status_code == 422


async def test_dashboard_skips_markets_already_served(user: AsyncClient) -> None:
    await save(user)
    dashboard = (await user.get("/api/v1/me/dashboard")).json()
    towels, bed_linen = dashboard["products"]
    assert towels["product"]["hs6"] == TOWELS and towels["total_markets"] == 3
    # Thailand ranks first for towels, but the user already sells there.
    assert [m["market"]["code"] for m in towels["top"]] == ["DEU", "USA"]
    assert [m["market"]["code"] for m in bed_linen["top"]] == ["USA"]
    assert dashboard["data"]["end_year"] == 2024


async def test_rankings_flag_markets_already_served(user: AsyncClient) -> None:
    await save(user)
    page = (await user.get(f"/api/v1/markets?exporter=PAK&hs6={TOWELS}")).json()
    flags = {i["market"]["code"]: i["already_selling"] for i in page["items"]}
    assert flags == {"THA": True, "DEU": False, "USA": False}


async def test_no_flags_when_browsing_another_exporter(user: AsyncClient) -> None:
    # An advisor whose own business is in Bangladesh, browsing Pakistan's exports:
    # their markets say nothing about Pakistan, so no personal flags.
    assert (await save(user, exporter="BGD", products=[TOWELS])).status_code == 200
    page = (await user.get(f"/api/v1/markets?exporter=PAK&hs6={TOWELS}")).json()
    assert page["items"] and not any(i["already_selling"] for i in page["items"])


async def test_all_countries_list(user: AsyncClient) -> None:
    names = [c["name"] for c in (await user.get("/api/v1/countries")).json()]
    assert names == sorted(names) and "Thailand" in names


async def test_best_moves_are_actionable_new_markets(user: AsyncClient) -> None:
    await save(user)  # sells to Thailand already
    moves = (await user.get("/api/v1/me/dashboard")).json()["best_moves"]
    picked = [(m["product"]["hs6"], m["market"]["market"]["code"]) for m in moves]
    # Thailand: already served. Germany: Pakistan holds 24% there, so "grow", not a new move.
    assert picked == [(BED_LINEN, "USA"), (TOWELS, "USA")]
    assert all(m["market"]["verdict"]["action"] in ("go", "test") for m in moves)
    assert moves[0]["market"]["verdict"]["summary"].endswith(".")


async def test_goal_defaults_to_selling(user: AsyncClient) -> None:
    assert (await save(user)).json()["goal"] == "sell"


async def test_buyers_need_supplier_data_not_markets(user: AsyncClient) -> None:
    buyer = await save(user, goal="buy", products=[TOWELS])
    assert buyer.status_code == 200 and buyer.json()["goal"] == "buy"
    # Bed linen has ranked markets (fine for selling) but no supplier data (not for buying).
    no_suppliers = await save(user, goal="buy", products=[BED_LINEN])
    assert no_suppliers.status_code == 422 and "supplier" in no_suppliers.json()["detail"]
    assert (await save(user, goal="trade")).status_code == 422


async def test_grow_range_suggests_close_relatives(user: AsyncClient) -> None:
    assert (await user.get("/api/v1/me/grow")).status_code == 404  # no profile yet
    await save(user, products=[TOWELS], current_markets=[])
    ideas = (await user.get("/api/v1/me/grow")).json()["ideas"]
    # Bed linen shares towels' heading (6302) and has a strong market; thread (chapter 52) doesn't.
    assert [(i["product"]["hs6"], i["same_family"]) for i in ideas] == [(BED_LINEN, True)]
    assert ideas[0]["top"]["market"]["code"] == "USA" and ideas[0]["strong_markets"] == 1
