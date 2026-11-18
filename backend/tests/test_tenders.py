"""EU tenders (matching, caching, outages, alerts) and company register checks."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.seed import TOWELS
from whitespace_api.core import tasks
from whitespace_api.core.config import Settings
from whitespace_api.core.http import http_client
from whitespace_api.integrations import ted
from whitespace_api.jobs import tenders as tender_job
from whitespace_api.main import app
from whitespace_api.models import Notification, TenderCache, UserProfile
from whitespace_api.services import tenders as service

TODAY = datetime.now(UTC).date()


def notice(
    number: str, title: str, cpv: list[str], *, days: int = 10, **extra: Any
) -> dict[str, Any]:
    return {
        "publication-number": number,
        "notice-title": {"eng": title, "deu": "x"},
        "buyer-name": {"fra": ["Ville de Lyon"]},
        "buyer-country": ["DEU"],
        "publication-date": f"{TODAY - timedelta(days=2)}+01:00",
        "deadline-receipt-tender-date-lot": [f"{TODAY + timedelta(days=days)}+01:00"],
        "classification-cpv": cpv,
        "estimated-value-lot": ["100000", "50000"],
        "estimated-value-cur-lot": ["EUR"],
    } | extra


NOTICES = [
    notice("1-2026", "France - Towels - Bath towels for hospitals", ["39514100"]),
    notice("2-2026", "France - Paper hand towels - Paper", ["33763000"]),  # other goods
    notice("3-2026", "France - Bed linen - Draps", ["39512000"]),  # no "towels"
    notice("4-2026", "France - Towels - Old", ["39514100"], days=-1),  # closed
]


def test_parse_and_match() -> None:
    parsed = ted.parse(NOTICES[0])
    assert parsed is not None and parsed.title.startswith("France - Towels")
    assert parsed.value == 150_000 and parsed.currency == "EUR" and parsed.countries == ("DEU",)
    assert parsed.url == "https://ted.europa.eu/en/notice/-/detail/1-2026"
    assert ted.parse({"no": "number"}) is None

    kept = service.select_tenders(
        [n for n in map(ted.parse, NOTICES) if n], hs6=TOWELS, name="towels", today=TODAY
    )
    assert [k["number"] for k in kept] == ["1-2026"] and kept[0]["match"] == "category"
    assert service.title_mentions("Italy - T-shirts - magliette", "t-shirts")
    assert not service.title_mentions("Germany - Shirts - Hemd", "t-shirts")
    assert service.title_mentions("Bed linen and towel sets", "bed linen")
    assert not service.title_mentions("Linen for the bed", "bed linen")
    assert service.cpv_prefixes("630260") == ("3951",) and service.cpv_prefixes("999999") == ()


# --- API ------------------------------------------------------------------------------


class Remote:
    """Fake TED / GLEIF / VIES. Set `.down` to simulate an outage."""

    def __init__(self) -> None:
        self.down = False
        self.ted_calls = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            return httpx.Response(503)
        host = request.url.host
        if host == "api.ted.europa.eu":
            self.ted_calls += 1
            body = json.loads(request.content)
            assert "notice-type IN (cn-standard cn-social)" in body["query"]
            return httpx.Response(200, json={"notices": NOTICES})
        if host == "api.gleif.org":
            assert request.url.params["filter[entity.legalAddress.country]"] == "DE"
            return httpx.Response(200, json={"data": [
                {"attributes": {"lei": "529900CN6W3UJGNAXM59", "entity": {
                    "legalName": {"name": "Holiday Heimtex GmbH & Co. KG"}, "status": "ACTIVE",
                    "legalAddress": {"city": "Seelbach", "country": "DE"},
                    "registeredAs": "HRA 707389"}, "registration": {"status": "ISSUED"}}},
                {"attributes": {"lei": "5299004YJOKHIGQWAL25", "entity": {
                    "legalName": {"name": "HOLIDAY HEIMTEX JOHANNES WAGNER e.K."},
                    "status": "INACTIVE", "legalAddress": {"city": "Seelbach", "country": "DE"}},
                    "registration": {"status": "RETIRED"}}},
            ]})  # fmt: skip
        if "vies" in request.url.path:
            body = json.loads(request.content)
            assert body["countryCode"] == "DE" and body["vatNumber"] == "811193231"
            return httpx.Response(200, json={"valid": True, "name": "---", "address": "---"})
        return httpx.Response(404)


@pytest.fixture
def remote(
    monkeypatch: pytest.MonkeyPatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> Iterator[Remote]:
    fake = Remote()
    client = httpx.AsyncClient(transport=httpx.MockTransport(fake.handler))
    app.dependency_overrides[http_client] = lambda: client
    monkeypatch.setattr(tender_job, "http_client", lambda: client)
    monkeypatch.setattr(tasks, "session_factory", db_sessionmaker)
    yield fake
    app.dependency_overrides.pop(http_client, None)


async def test_tenders_cached_and_shown_stale_when_ted_is_down(
    user: AsyncClient, remote: Remote, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    first = (await user.get(f"/api/v1/tenders/{TOWELS}")).json()
    assert [t["number"] for t in first["tenders"]] == ["1-2026"]
    t = first["tenders"][0]
    assert t["country_names"] == ["Germany"] and t["days_left"] == 10 and not first["stale"]
    await user.get(f"/api/v1/tenders/{TOWELS}")
    assert remote.ted_calls == 1  # served from the cache

    async with db_sessionmaker() as db:  # age the cache, then take TED down
        await db.execute(
            update(TenderCache).values(fetched_at=datetime.now(UTC) - timedelta(days=1))
        )
        await db.commit()
    remote.down = True
    stale = (await user.get(f"/api/v1/tenders/{TOWELS}")).json()
    assert stale["stale"] is True and len(stale["tenders"]) == 1

    assert (await user.get("/api/v1/tenders/999999")).status_code == 404


async def test_no_cache_and_ted_down_is_503(user: AsyncClient, remote: Remote) -> None:
    remote.down = True
    assert (await user.get(f"/api/v1/tenders/{TOWELS}")).status_code == 503


async def profile(db_sessionmaker: async_sessionmaker[AsyncSession], user: AsyncClient) -> None:
    me = (await user.get("/api/v1/auth/me")).json()["id"]
    async with db_sessionmaker() as db:
        db.add(UserProfile(user_id=me, exporter="PAK", role="exporter", products=[TOWELS]))
        await db.commit()


async def test_my_tenders_and_alerts_once(
    user: AsyncClient, remote: Remote, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await profile(db_sessionmaker, user)
    mine = (await user.get("/api/v1/tenders")).json()
    assert mine["products"] == ["towels"] and len(mine["tenders"]) == 1

    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert (await tender_job.run(settings)).endswith("1 tender alerts")
    assert (await tender_job.run(settings)).endswith("0 tender alerts")  # never twice
    async with db_sessionmaker() as db:
        note = await db.scalar(select(Notification))
    assert note is not None and note.kind == "tender" and note.link == "/app/tenders"
    assert "Bath towels" in note.title


async def test_company_checks(user: AsyncClient, remote: Remote) -> None:
    check = await user.get(
        "/api/v1/companies/check", params={"name": "Holiday Heimtex GmbH", "country": "DEU"}
    )
    body = check.json()
    assert body["available"] is True
    best = body["matches"][0]
    assert best["exact"] and best["active"] and best["registered_as"] == "HRA 707389"
    assert best["url"].endswith("529900CN6W3UJGNAXM59")
    assert body["matches"][1]["active"] is False

    vat = await user.post(
        "/api/v1/companies/vat", json={"country": "DEU", "number": "DE 811193231"}
    )
    assert vat.json()["valid"] is True and vat.json()["number"] == "DE811193231"
    assert vat.json()["name"] is None  # Germany doesn't disclose names: shown as unknown
    outside = await user.post("/api/v1/companies/vat", json={"country": "USA", "number": "12345"})
    assert outside.status_code == 422

    remote.down = True
    down = await user.get(
        "/api/v1/companies/check", params={"name": "Holiday Heimtex", "country": "DEU"}
    )
    assert down.json()["available"] is False and down.json()["matches"] == []
    vat_down = await user.post(
        "/api/v1/companies/vat", json={"country": "DEU", "number": "811193231"}
    )
    assert vat_down.status_code == 503


def test_dates_are_parsed_without_timezone_suffix() -> None:
    assert ted._day("2026-11-23+01:00") == date(2026, 11, 23)
    assert ted._day("nonsense") is None and ted._day(None) is None
