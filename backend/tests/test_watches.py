"""Watchlists and the bell: validation, idempotency, the limit, races, and privacy."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.seed import THREAD, TOWELS
from whitespace_api.core.config import Settings, get_settings
from whitespace_api.main import app
from whitespace_api.models import Notification, User, Watch

PROFILE = {"exporter": "PAK", "role": "exporter", "products": [TOWELS], "current_markets": []}
GERMANY = {"hs6": TOWELS, "market": "DEU"}


@pytest.fixture
async def seller(user: AsyncClient) -> AsyncClient:
    assert (await user.put("/api/v1/me/profile", json=PROFILE)).status_code == 200
    return user


def use_settings(**values: Any) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, **values)  # type: ignore[call-arg]


async def watch(client: AsyncClient, **body: str) -> Response:
    return await client.post("/api/v1/watches", json=body)


async def become_someone_else(client: AsyncClient) -> None:
    """Same client, new identity: registering signs the client in as the new user."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "full_name": "Other", "password": "towels-2026!"},
    )
    assert response.status_code == 201


async def test_requires_sign_in(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/watches")).status_code == 401
    assert (await client.post("/api/v1/watches", json=GERMANY)).status_code == 401
    assert (await client.get("/api/v1/watches/check", params=GERMANY)).status_code == 401
    assert (await client.delete(f"/api/v1/watches/{uuid.uuid4()}")).status_code == 401
    assert (await client.get("/api/v1/notifications")).status_code == 401
    read_all = await client.post("/api/v1/notifications/read", json={"all": True})
    assert read_all.status_code == 401


# ---------- watches ----------
async def test_watch_defaults_to_the_profile_country(seller: AsyncClient) -> None:
    response = await watch(seller, **GERMANY)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["exporter"] == {"code": "PAK", "name": "Pakistan"}
    assert body["product"]["hs6"] == TOWELS and body["product"]["name"] == "towels"
    assert body["market"] == {"code": "DEU", "name": "Germany"}
    assert body["alerts_available"] is True
    assert [w["id"] for w in (await seller.get("/api/v1/watches")).json()] == [body["id"]]


async def test_watching_twice_returns_the_existing_watch(seller: AsyncClient) -> None:
    first = await watch(seller, **GERMANY)
    again = await watch(seller, exporter="PAK", **GERMANY)
    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json()["id"] == first.json()["id"]
    assert len((await seller.get("/api/v1/watches")).json()) == 1


async def test_simultaneous_watches_make_one(seller: AsyncClient) -> None:
    responses = await asyncio.gather(*(watch(seller, **GERMANY) for _ in range(3)))
    assert sorted(r.status_code for r in responses) == [200, 200, 201]
    assert len({r.json()["id"] for r in responses}) == 1


async def test_check_for_a_watch_toggle(seller: AsyncClient) -> None:
    check = "/api/v1/watches/check"
    assert (await seller.get(check, params=GERMANY)).json() == {"watching": False, "id": None}
    created = (await watch(seller, **GERMANY)).json()
    assert (await seller.get(check, params=GERMANY)).json() == {
        "watching": True,
        "id": created["id"],
    }
    # The same market seen as another exporter is a different watch.
    other = await seller.get(check, params={**GERMANY, "exporter": "BGD"})
    assert other.json()["watching"] is False


async def test_rejects_what_cannot_be_watched(seller: AsyncClient) -> None:
    assert (await watch(seller, hs6="63026", market="DEU")).status_code == 422
    assert (await watch(seller, hs6=TOWELS, market="deu")).status_code == 422
    assert (await watch(seller, exporter="pak", **GERMANY)).status_code == 422
    unranked = await watch(seller, hs6=THREAD, market="DEU")  # a real product, no ranked markets
    assert unranked.status_code == 422 and "isn't a ranked market" in unranked.json()["detail"]
    assert (await watch(seller, hs6=TOWELS, market="FRA")).status_code == 422
    malformed = await seller.get("/api/v1/watches/check", params={"hs6": "x", "market": "DEU"})
    assert malformed.status_code == 422


async def test_without_a_profile_the_exporter_is_needed(user: AsyncClient) -> None:
    response = await watch(user, **GERMANY)
    assert response.status_code == 422 and "profile" in response.json()["detail"]
    explicit = await watch(user, exporter="BGD", hs6=TOWELS, market="THA")
    assert explicit.status_code == 201 and explicit.json()["exporter"]["code"] == "BGD"
    status = await user.get("/api/v1/watches/check", params=GERMANY)
    assert status.json() == {"watching": False, "id": None}


async def test_watch_limit(seller: AsyncClient) -> None:
    use_settings(watch_limit=2)
    assert (await watch(seller, **GERMANY)).status_code == 201
    assert (await watch(seller, hs6=TOWELS, market="USA")).status_code == 201
    full = await watch(seller, hs6=TOWELS, market="THA")
    assert full.status_code == 409 and "already watching 2 markets" in full.json()["detail"]
    assert (await watch(seller, **GERMANY)).status_code == 200  # re-watching still answers
    assert len((await seller.get("/api/v1/watches")).json()) == 2


async def test_simultaneous_watches_cannot_pass_the_limit(seller: AsyncClient) -> None:
    use_settings(watch_limit=1)
    markets = ("DEU", "USA", "THA")
    responses = await asyncio.gather(*(watch(seller, hs6=TOWELS, market=m) for m in markets))
    assert sorted(r.status_code for r in responses) == [201, 409, 409]
    assert len((await seller.get("/api/v1/watches")).json()) == 1


async def test_which_markets_can_alert(seller: AsyncClient) -> None:
    for market in ("DEU", "USA", "THA"):
        assert (await watch(seller, hs6=TOWELS, market=market)).status_code == 201

    async def flags() -> dict[str, bool]:
        listed = (await seller.get("/api/v1/watches")).json()
        return {w["market"]["code"]: w["alerts_available"] for w in listed}

    # Thailand has no monthly source; US data needs a Census key, which tests don't set.
    assert await flags() == {"DEU": True, "USA": False, "THA": False}
    use_settings(census_api_key="test-key")
    assert await flags() == {"DEU": True, "USA": True, "THA": False}


async def test_stop_watching(seller: AsyncClient) -> None:
    created = (await watch(seller, **GERMANY)).json()
    assert (await seller.delete(f"/api/v1/watches/{created['id']}")).status_code == 204
    assert (await seller.delete(f"/api/v1/watches/{created['id']}")).status_code == 404
    assert (await seller.get("/api/v1/watches")).json() == []
    assert (await seller.delete("/api/v1/watches/not-a-uuid")).status_code == 422


async def test_watches_are_private(
    seller: AsyncClient, client: AsyncClient, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    created = (await watch(seller, **GERMANY)).json()
    await become_someone_else(client)
    assert (await client.get("/api/v1/watches")).json() == []
    assert (await client.delete(f"/api/v1/watches/{created['id']}")).status_code == 404
    status = await client.get("/api/v1/watches/check", params={**GERMANY, "exporter": "PAK"})
    assert status.json()["watching"] is False
    async with db_sessionmaker() as s:  # the owner's watch is untouched
        assert await s.get(Watch, uuid.UUID(created["id"])) is not None


# ---------- notifications ----------
async def notify(
    db_sessionmaker: async_sessionmaker[AsyncSession], email: str, count: int
) -> list[uuid.UUID]:
    """`count` unread notifications for the user, a day apart, oldest first."""
    async with db_sessionmaker() as s:
        owner = (await s.scalars(select(User.id).where(User.email == email))).one()
        rows = [
            Notification(
                user_id=owner,
                kind="imports_up",
                title=f"Towels in Germany: imports up {21 + i}%",
                body="Germany imported more towels.",
                link=f"/app/markets/{TOWELS}/DEU?exporter=PAK",
                data={"tone": "positive"},
                dedupe_key=f"imports_up:PAK:{TOWELS}:DEU:2026-0{i + 1}",
                created_at=datetime(2026, 9, 1, tzinfo=UTC) + timedelta(days=i),
            )
            for i in range(count)
        ]
        s.add_all(rows)
        await s.commit()
        return [r.id for r in rows]


async def test_notifications_newest_first_with_unread_count(
    seller: AsyncClient, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    ids = await notify(db_sessionmaker, "ahmed@example.com", 3)
    page = (await seller.get("/api/v1/notifications")).json()
    assert page["unread"] == 3
    assert [n["id"] for n in page["items"]] == [str(i) for i in reversed(ids)]
    newest = page["items"][0]
    assert newest["kind"] == "imports_up" and newest["read_at"] is None
    assert newest["link"] == f"/app/markets/{TOWELS}/DEU?exporter=PAK"
    assert newest["data"] == {"tone": "positive"}
    one = (await seller.get("/api/v1/notifications", params={"limit": 1})).json()
    assert len(one["items"]) == 1 and one["unread"] == 3  # the count covers them all
    assert (await seller.get("/api/v1/notifications", params={"limit": 0})).status_code == 422


async def test_mark_read(
    seller: AsyncClient, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    ids = await notify(db_sessionmaker, "ahmed@example.com", 3)
    first = await seller.post("/api/v1/notifications/read", json={"ids": [str(ids[0])]})
    assert first.status_code == 200 and first.json() == {"unread": 2}
    items = {n["id"]: n for n in (await seller.get("/api/v1/notifications")).json()["items"]}
    assert items[str(ids[0])]["read_at"] is not None and items[str(ids[1])]["read_at"] is None
    everything = await seller.post("/api/v1/notifications/read", json={"all": True})
    assert everything.json() == {"unread": 0}


@pytest.mark.parametrize(
    "body",
    [{}, {"all": False}, {"ids": []}, {"ids": [str(uuid.uuid4())], "all": True}, {"ids": ["x"]}],
)
async def test_mark_read_needs_ids_or_all(seller: AsyncClient, body: dict[str, Any]) -> None:
    assert (await seller.post("/api/v1/notifications/read", json=body)).status_code == 422


async def test_notifications_are_private(
    seller: AsyncClient, client: AsyncClient, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    ids = await notify(db_sessionmaker, "ahmed@example.com", 2)
    await become_someone_else(client)
    assert (await client.get("/api/v1/notifications")).json() == {"unread": 0, "items": []}
    # Marking someone else's notifications read changes nothing and reveals nothing.
    theirs = {"ids": [str(i) for i in ids]}
    assert (await client.post("/api/v1/notifications/read", json=theirs)).json() == {"unread": 0}
    assert (await client.post("/api/v1/notifications/read", json={"all": True})).status_code == 200
    async with db_sessionmaker() as s:
        unread = (await s.scalars(select(Notification).where(Notification.read_at.is_(None)))).all()
    assert len(unread) == 2
