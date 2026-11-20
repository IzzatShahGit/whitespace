"""Buyer checks: list parsers, the atomic list refresh, name matching, domain rules, and
the whole check through the API with the outside services mocked."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.seed import TOWELS
from whitespace_api.core import tasks
from whitespace_api.core.config import Settings, get_settings
from whitespace_api.core.http import http_client
from whitespace_api.integrations import sanctions
from whitespace_api.jobs import sanctions as job
from whitespace_api.main import app
from whitespace_api.models import Country
from whitespace_api.models.screening import SanctionName
from whitespace_api.services import buyer_check, outreach, screening

OFAC_SDN = (
    '36,"AEROCARIBBEAN AIRLINES",-0- ,"CUBA",-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- \n'
    '9647,"MAHAN AIR",-0- ,"SDGT] [IRAN",-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- \n'
    '15037,"SHAHID BAKERI","vessel","IRAN",-0- ,-0- ,"Crude Oil Tanker",-0- ,-0- \n'
    '7777,"HUSSEIN, Saddam",individual,"IRAQ2",-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- \n'
)
OFAC_ALT = '9647,1,"aka","MAHAN AIRLINES",-0- \n15037,2,"aka","BAKERI TANKER",-0- \n'
UN_XML = """<?xml version="1.0" encoding="UTF-8"?>
<CONSOLIDATED_LIST><INDIVIDUALS><INDIVIDUAL><DATAID>1</DATAID><FIRST_NAME>ABDUL</FIRST_NAME>
<SECOND_NAME>BAQI</SECOND_NAME><UN_LIST_TYPE>Taliban</UN_LIST_TYPE>
<REFERENCE_NUMBER>TAi.001</REFERENCE_NUMBER><INDIVIDUAL_ALIAS><ALIAS_NAME>Abdul Baqi Basir
</ALIAS_NAME></INDIVIDUAL_ALIAS></INDIVIDUAL></INDIVIDUALS><ENTITIES><ENTITY><DATAID>2</DATAID>
<FIRST_NAME>AL-RASHID TRUST</FIRST_NAME><UN_LIST_TYPE>Al-Qaida</UN_LIST_TYPE>
<REFERENCE_NUMBER>QDe.005</REFERENCE_NUMBER><ENTITY_ALIAS><ALIAS_NAME>Al Rasheed Trust</ALIAS_NAME>
</ENTITY_ALIAS><ENTITY_ALIAS><ALIAS_NAME /></ENTITY_ALIAS></ENTITY></ENTITIES></CONSOLIDATED_LIST>
"""
EU_HEAD = (
    "﻿fileGenerationDate;Entity_LogicalId;Entity_SubjectType;NameAlias_WholeName;"
    "Entity_Regulation_Programme;Entity_Regulation_PublicationUrl\n"
)
EU_CSV = EU_HEAD + (
    "2026-11-19;13;P;Saddam Hussein Al-Tikriti;IRQ;https://eur-lex.europa.eu/a\n"
    "2026-11-19;13;P;Saddam Hussein Al-Tikriti;IRQ;https://eur-lex.europa.eu/a\n"
    "2026-11-19;99;E;JSC Sovcomflot;RUS;https://eur-lex.europa.eu/b\n"
)
UK_CSV = (
    "Report Date: 17-Nov-2026\n"
    "Unique ID,Name 6,Name 1,Name 2,Name 3,Name 4,Name 5,Name type,Regime Name,Designation Type\n"
    "RUS0001,PAO SOVCOMFLOT,,,,,,Primary Name,Russia,Entity\n"
    "RUS0001,PAO SOVCOMFLOT,,,,,,Primary Name,Russia,Entity\n"
    "RUS0002,PETROV,Ivan,,,,,Primary Name,Russia,Individual\n"
    "RUS0003,NS ARCTIC,,,,,,Primary Name,Russia,Ship\n"
)
FILES = {"ofac": [OFAC_SDN, OFAC_ALT], "un": [UN_XML], "eu": [EU_CSV], "uk": [UK_CSV]}


def write(tmp: Path, *texts: str) -> list[Path]:
    paths = []
    for i, text in enumerate(texts):
        path = tmp / f"{i}.dat"
        path.write_text(text, encoding="utf-8")
        paths.append(path)
    return paths


# --- parsers -------------------------------------------------------------------------


def test_parsers_read_names_and_aliases_and_skip_ships(tmp_path: Path) -> None:
    ofac = list(sanctions.parse("ofac", write(tmp_path, OFAC_SDN, OFAC_ALT)))
    assert {(x.ref, x.kind, x.name) for x in ofac} == {
        ("36", "entity", "AEROCARIBBEAN AIRLINES"),
        ("9647", "entity", "MAHAN AIR"),
        ("9647", "entity", "MAHAN AIRLINES"),
        ("7777", "individual", "HUSSEIN, Saddam"),
    }  # the tanker and its alias are skipped
    assert ofac[1].url == "https://sanctionssearch.ofac.treas.gov/Details.aspx?id=9647"

    un = list(sanctions.parse("un", write(tmp_path, UN_XML)))
    assert [(x.ref, x.kind, x.name) for x in un] == [
        ("TAi.001", "individual", "ABDUL BAQI"),
        ("TAi.001", "individual", "Abdul Baqi Basir"),
        ("QDe.005", "entity", "AL-RASHID TRUST"),
        ("QDe.005", "entity", "Al Rasheed Trust"),
    ]
    eu = list(sanctions.parse("eu", write(tmp_path, EU_CSV)))
    assert [(x.ref, x.kind, x.name, x.url) for x in eu] == [
        ("13", "individual", "Saddam Hussein Al-Tikriti", "https://eur-lex.europa.eu/a"),
        ("99", "entity", "JSC Sovcomflot", "https://eur-lex.europa.eu/b"),
    ]  # duplicate rows collapse
    uk = list(sanctions.parse("uk", write(tmp_path, UK_CSV)))
    assert [(x.ref, x.kind, x.name) for x in uk] == [
        ("RUS0001", "entity", "PAO SOVCOMFLOT"),
        ("RUS0002", "individual", "Ivan PETROV"),
    ]


# --- the refresh job -----------------------------------------------------------------


@pytest.fixture
def lists(
    monkeypatch: pytest.MonkeyPatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> Iterator[list[str]]:
    """Downloads served from the fixtures above; records each URL fetched."""
    fetched: list[str] = []
    by_url = {
        url: text
        for key, texts in FILES.items()
        for url, text in zip(sanctions.SOURCES[key].files, texts, strict=True)
    }

    async def fake(client: Any, url: str, path: Path, digest: hashlib._Hash) -> None:
        fetched.append(url)
        data = by_url[url].encode()
        path.write_bytes(data)  # noqa: ASYNC240  (a few bytes, in a test)
        digest.update(data)

    monkeypatch.setattr(sanctions, "download", fake)
    monkeypatch.setattr(tasks, "session_factory", db_sessionmaker)
    yield fetched


async def test_refresh_loads_each_list_and_skips_unchanged(
    lists: list[str], db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    summary = await job.run(Settings(_env_file=None))  # type: ignore[call-arg]
    assert summary == "ofac: 4 names, un: 4 names, eu: 2 names, uk: 2 names"
    again = await job.run(Settings(_env_file=None))  # type: ignore[call-arg]
    assert again == "ofac: unchanged, un: unchanged, eu: unchanged, uk: unchanged"
    async with db_sessionmaker() as db:
        assert await db.scalar(select(func.count()).select_from(SanctionName)) == 12
        status = {s.source: s for s in await screening.lists(db)}
        assert status["ofac"].names == 4 and status["ofac"].loaded_at is not None
        # "JSC Sovcomflot" and "PAO SOVCOMFLOT" are stored as the same comparable name.
        cores = set(await db.scalars(select(SanctionName.name_core)))
        assert {"sovcomflot", "mahan air", "aerocaribbean airlines"} <= cores


async def test_a_failing_list_keeps_its_old_copy(
    lists: list[str],
    monkeypatch: pytest.MonkeyPatch,
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    await job.run(Settings(_env_file=None))  # type: ignore[call-arg]

    async def down(*_: Any) -> None:
        raise httpx.ConnectError("down")

    monkeypatch.setattr(sanctions, "download", down)
    summary = await job.run(Settings(_env_file=None), sources=["uk"])  # type: ignore[call-arg]
    assert summary == "uk: failed"
    async with db_sessionmaker() as db:
        uk = next(s for s in await screening.lists(db) if s.source == "uk")
        assert uk.names == 2 and uk.error and "down" in uk.error


# --- matching ------------------------------------------------------------------------


def test_grading_is_strict_about_generic_and_short_names() -> None:
    assert screening.grade("mahan air", "mahan air") == (1.0, "strong")
    assert screening.grade("mahan airline", "mahan air")[1] == "possible"  # a variant
    assert screening.grade("sovcomflot", "sovcomflot")[1] == "strong"
    assert screening.grade("rosneft", "rosneft aero")[1] == "possible"
    assert screening.grade("alfa", "kgb alfa")[1] is None  # short word inside a name
    assert screening.grade("global trading", "global trading")[1] == "possible"
    assert screening.grade("global trading", "global import")[1] is None  # generic only
    assert screening.grade("hansen textil", "hansa textiles")[1] is None


async def test_screen_finds_aliases_and_ignores_other_kinds(
    lists: list[str], db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await job.run(Settings(_env_file=None))  # type: ignore[call-arg]
    async with db_sessionmaker() as db:
        hits = await screening.screen(db, "Mahan Airlines Co.")
        assert [(h.source, h.grade) for h in hits] == [("ofac", "strong")]
        assert {h.source for h in await screening.screen(db, "Sovcomflot")} == {"eu", "uk"}
        assert await screening.screen(db, "Petrov Ivan") == []  # a person, not a company
        assert [h.ref for h in await screening.screen(db, "Ivan Petrov", kind="individual")] == [
            "RUS0002"
        ]
        assert await screening.screen(db, "Holiday Heimtex GmbH") == []


# --- domain rules --------------------------------------------------------------------


def test_domains() -> None:
    assert buyer_check.registrable("shop.hansen-textil.co.uk") == "hansen-textil.co.uk"
    assert buyer_check.website_domain("www.Hansen-Textil.de/kontakt") == "hansen-textil.de"
    assert buyer_check.email_domain("Klaus@Mail.Hansen-Textil.de") == "hansen-textil.de"
    assert buyer_check.is_webmail("yahoo.co.uk") and buyer_check.is_webmail("gmail.com")
    assert not buyer_check.is_webmail("hansen-textil.de")
    assert buyer_check.lookalike("hansentextil.com", "hansen-textil.de")
    assert buyer_check.lookalike("hansen-texti1.de", "hansen-textil.de")
    assert not buyer_check.lookalike("tchibo-group.com", "hansen-textil.de")


# --- the whole check -----------------------------------------------------------------


def outside(registered: dict[str, str], *, lei: bool = True, vat_valid: bool = True) -> Any:
    def handle(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "gleif" in url:
            rows = [
                {
                    "attributes": {
                        "lei": "529900ABC",
                        "entity": {
                            "legalName": {"name": "Holiday Heimtex GmbH & Co. KG"},
                            "legalAddress": {"city": "Bremen", "country": "DE"},
                            "status": "ACTIVE",
                            "registeredAs": "HRA 1",
                        },
                        "registration": {"status": "ISSUED"},
                    }
                }
            ]
            return httpx.Response(200, json={"data": rows if lei else []})
        if "rdap" in url:
            domain = url.rsplit("/", 1)[-1]
            if domain not in registered:
                return httpx.Response(404)
            events = [{"eventAction": "registration", "eventDate": registered[domain]}]
            return httpx.Response(200, json={"events": events})
        if "vies" in url:
            assert json.loads(request.content)["vatNumber"]
            return httpx.Response(200, json={"valid": vat_valid, "name": "Holiday Heimtex GmbH"})
        return httpx.Response(503)

    return httpx.AsyncClient(transport=httpx.MockTransport(handle))


async def contact(user: AsyncClient, **extra: Any) -> dict[str, Any]:
    body = {"hs6": TOWELS, "market": "DEU", "name": "Holiday Heimtex GmbH"} | extra
    return (await user.post("/api/v1/pipeline", json=body)).json()["contact"]


async def test_a_clean_buyer_is_green(user: AsyncClient, lists: list[str]) -> None:
    await job.run(Settings(_env_file=None))  # type: ignore[call-arg]
    old = (datetime.now(UTC) - timedelta(days=9000)).isoformat()
    app.dependency_overrides[http_client] = lambda: outside({"holiday-heimtex.de": old})
    try:
        c = await contact(user, website="https://www.holiday-heimtex.de")
        body = {"name": c["name"], "country": "DEU", "contact_id": c["id"], "vat": "DE123456789",
                "email": "einkauf@holiday-heimtex.de"}  # fmt: skip
        out = (await user.post("/api/v1/buyer-checks", json=body)).json()
    finally:
        app.dependency_overrides.pop(http_client, None)
    assert out["verdict"] == "green", out["findings"]
    codes = [f["code"] for f in out["findings"]]
    assert set(codes) == {"sanctions_clear", "register_found", "vat_valid", "domain_age"}
    assert out["website_domain"] == out["email_domain"] == "holiday-heimtex.de"
    cards = (await user.get("/api/v1/pipeline")).json()
    assert cards[0]["check_verdict"] == "green"
    kept = (await user.get(f"/api/v1/buyer-checks/contacts/{c['id']}")).json()
    assert kept["verdict"] == "green" and kept["checked_at"] == out["checked_at"]


@pytest.fixture
async def iran(db_sessionmaker: async_sessionmaker[AsyncSession], seeded: None) -> None:
    async with db_sessionmaker() as db:
        db.add(Country(code="IRN", name="Iran"))
        await db.commit()


async def test_a_scam_inquiry_is_red_with_every_reason(
    user: AsyncClient, lists: list[str], iran: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    def offline(spec: Any, settings: Any = None) -> Any:
        raise RuntimeError("no model in tests")

    monkeypatch.setattr(outreach.llm, "get_chat_model", offline)
    await job.run(Settings(_env_file=None))  # type: ignore[call-arg]
    new = (datetime.now(UTC) - timedelta(days=12)).isoformat()
    old = (datetime.now(UTC) - timedelta(days=9000)).isoformat()
    app.dependency_overrides[http_client] = lambda: outside(
        {"holiday-heimtex.de": old, "holidayheimtex.com": new}, lei=False, vat_valid=False
    )
    try:
        c = await contact(user, website="https://holiday-heimtex.de")
        reply = "Our bank account has been changed. Pay the registration fee first."
        logged = await user.post(f"/api/v1/pipeline/{c['id']}/replies", json={"text": reply})
        assert logged.status_code == 201
        body = {"name": "Mahan Airlines", "country": "IRN", "contact_id": c["id"],
                "vat": "DE1", "email": "buyer@holidayheimtex.com"}  # fmt: skip
        out = (await user.post("/api/v1/buyer-checks", json=body)).json()
    finally:
        app.dependency_overrides.pop(http_client, None)
    assert out["verdict"] == "red"
    codes = [f["code"] for f in out["findings"]]
    assert {
        "sanctions_match", "lookalike_domain", "domain_new", "wording_bank_change",
        "wording_advance_fee", "country_restricted", "register_none",
    } <= set(codes)  # fmt: skip
    assert "vat_invalid" not in codes  # VAT is only checked for EU countries
    severities = [f["severity"] for f in out["findings"]]
    assert severities == sorted(severities, key=lambda s: buyer_check.RANK[s])  # worst first
    assert out["sanctions"][0]["url"].endswith("id=9647")


async def test_missing_lists_never_look_clean(user: AsyncClient) -> None:
    app.dependency_overrides[http_client] = lambda: outside({}, lei=False)
    try:
        out = (
            await user.post("/api/v1/buyer-checks", json={"name": "Vossen", "country": "DEU"})
        ).json()
    finally:
        app.dependency_overrides.pop(http_client, None)
    assert out["verdict"] == "amber"
    assert "sanctions_incomplete" in [f["code"] for f in out["findings"]]
    lists = (await user.get("/api/v1/buyer-checks/lists")).json()
    assert [entry["source"] for entry in lists] == ["ofac", "un", "eu", "uk"]
    assert all(entry["names"] == 0 for entry in lists)


async def test_limits_validation_and_privacy(user: AsyncClient) -> None:
    app.dependency_overrides[http_client] = lambda: outside({})
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,  # type: ignore[call-arg]
        buyer_check_daily_limit=1,
    )
    try:
        bad = await user.post(
            "/api/v1/buyer-checks", json={"name": "X Ltd", "country": "DEU", "email": "nope"}
        )
        assert bad.status_code == 422
        body = {"name": "Vossen", "country": "DEU"}
        assert (await user.post("/api/v1/buyer-checks", json=body)).status_code == 200
        limited = await user.post("/api/v1/buyer-checks", json=body)
        assert limited.status_code == 429
        c = await contact(user)
    finally:
        app.dependency_overrides.pop(http_client, None)
        app.dependency_overrides.pop(get_settings, None)
    await user.post(
        "/api/v1/auth/register",
        json={"email": "rival@example.com", "full_name": "Rival", "password": "towels-2026!"},
    )
    theirs = {"name": "Holiday", "country": "DEU", "contact_id": c["id"]}
    assert (await user.post("/api/v1/buyer-checks", json=theirs)).status_code == 404
    assert (await user.get(f"/api/v1/buyer-checks/contacts/{c['id']}")).status_code == 404
