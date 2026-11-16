"""Import duties and landed cost: source parsing, preference resolution, caching, the API
and the guide's duty tool. Sources are recorded responses (tests/fixtures): no network.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import RunnableLambda
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.seed import TOWELS
from whitespace_api.agents.chat import tools
from whitespace_api.agents.llm import CallSpec
from whitespace_api.core import tasks
from whitespace_api.core.config import Settings
from whitespace_api.core.http import http_client
from whitespace_api.integrations import tariffs
from whitespace_api.main import app
from whitespace_api.models import Country, MarketOpportunity, MarketSupplier, TariffCache
from whitespace_api.schemas.trade import CountryOut
from whitespace_api.services import chat as chat_service
from whitespace_api.services import landed_cost

FIXTURES = Path(__file__).parent / "fixtures"
NO_RECORDS = httpx.Response(404, text="Not Found - NoRecordsFound")
WITS_FILES = {
    ("918", "000", "all"): "wits_918_630260_mfn.xml",
    ("918", "all", "2021"): "wits_918_630260_2021.xml",
    ("918", "B29", "all"): "wits_918_630260_B29.xml",
    ("840", "000", "all"): "wits_840_630260_mfn.xml",
    ("840", "all", "2021"): "wits_840_630260_2021.xml",
}


def recorded(request: httpx.Request) -> httpx.Response:
    """The sources as recorded in November 2026, for towels (630260)."""
    url = str(request.url)
    if url.startswith(tariffs.UK_URL):
        if url.endswith("/headings/6302"):
            return httpx.Response(200, content=(FIXTURES / "uk_heading_6302.json").read_bytes())
        if "/commodities/630260" in url:  # both towel lines share one recorded document
            body = (FIXTURES / "uk_commodity_6302600090.json").read_bytes()
            return httpx.Response(200, content=body)
        return httpx.Response(404, json={"errors": [{"detail": "not found"}]})
    parts = url.split("/")
    key = tuple(parts[parts.index(name) + 1] for name in ("reporter", "partner", "year"))
    name = WITS_FILES.get(key)  # type: ignore[arg-type]
    return httpx.Response(200, content=(FIXTURES / name).read_bytes()) if name else NO_RECORDS


def down(request: httpx.Request) -> httpx.Response:
    return httpx.Response(503)


@dataclass
class Source:
    """The fake tariff sources the API talks to, and the URLs it asked for."""

    handler: Callable[[httpx.Request], httpx.Response] = recorded
    calls: list[str] = field(default_factory=list)

    def client(self) -> httpx.AsyncClient:
        def record(request: httpx.Request) -> httpx.Response:
            self.calls.append(str(request.url))
            return self.handler(request)

        return httpx.AsyncClient(transport=httpx.MockTransport(record))


@pytest.fixture
def source() -> Iterator[Source]:
    fake = Source()
    client = fake.client()
    app.dependency_overrides[http_client] = lambda: client
    yield fake


@pytest.fixture
async def markets(seeded: None, db_sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    """Germany also buys from the Netherlands (EU) and Türkiye; the US and UK from China."""
    async with db_sessionmaker() as s:
        s.add_all(
            [
                Country(code=c, name=n)
                for c, n in [("NLD", "Netherlands"), ("TUR", "Türkiye"), ("GBR", "United Kingdom")]
            ]
        )
        await s.flush()

        def supplier(market: str, code: str, share: float, price: float | None) -> MarketSupplier:
            return MarketSupplier(
                market=market, hs6=TOWELS, supplier=code, value_usd=share * 1e7,
                share_start=share, share_end=share, unit_price_usd_kg=price,
            )  # fmt: skip

        s.add_all(
            [
                supplier("DEU", "TUR", 0.15, 3.8),
                supplier("DEU", "NLD", 0.10, 5.0),
                supplier("USA", "CHN", 0.6, 4.0),
                supplier("GBR", "CHN", 0.4, 4.5),
            ]
        )
        await s.execute(
            update(MarketOpportunity)
            .where(MarketOpportunity.market == "DEU", MarketOpportunity.hs6 == TOWELS)
            .values(market_unit_price_usd_kg=4.0)
        )
        await s.commit()


def url(market: str, kind: str = "duties", **params: Any) -> str:
    query = "&".join(f"{k}={v}" for k, v in {"exporter": "PAK", "hs6": TOWELS, **params}.items())
    return f"/api/v1/markets/{market}/{kind}?{query}"


# ---------- sources ----------
def test_wits_parsing() -> None:
    rows = tariffs.parse_wits((FIXTURES / "wits_918_630260_2021.xml").read_bytes())
    by_partner = {r["partner"]: r for r in rows}
    assert by_partner["000"] == {
        "partner": "000", "kind": "MFN", "year": 2021, "rate": 12.0, "min_rate": 12.0,
        "max_rate": 12.0, "lines": 2, "na_lines": 0, "scheme": None,
    }  # fmt: skip
    # Country codes become ISO alpha-3; group codes stay as they are.
    assert by_partner["VNM"]["rate"] == 8.0 and by_partner["TUR"]["rate"] == 0.0
    assert by_partner["A87"]["rate"] == 9.6 and "GBR" in by_partner
    mfn = tariffs.parse_wits((FIXTURES / "wits_840_630260_mfn.xml").read_bytes())
    assert {r["year"]: r["rate"] for r in mfn} == {
        2021: 9.1,
        2022: 9.1,
        2023: 9.1,
    }  # no float noise


def test_wits_comtrade_codes_and_unsafe_xml() -> None:
    body = (
        b'<m xmlns:m="x"><Series PARTNER="699"><Obs TIME_PERIOD="2021" OBS_VALUE="5" '
        b'TARIFFTYPE="PREF" /></Series><Series PARTNER="842"><Obs TIME_PERIOD="2021" '
        b'OBS_VALUE="0" TARIFFTYPE="PREF" /></Series></m>'
    )
    assert [r["partner"] for r in tariffs.parse_wits(body)] == ["IND", "USA"]
    with pytest.raises(tariffs.SourceError):
        tariffs.parse_wits(b'<!DOCTYPE x [<!ENTITY a "aaaa">]><x>&a;</x>')


@pytest.mark.parametrize(
    ("market", "reporter"),
    [("DEU", "918"), ("FRA", "918"), ("POL", "918"), ("USA", "840"), ("GBR", "826"),
     ("PAK", "586"), ("IND", "356"), ("S19", None)],
)  # fmt: skip
def test_reporters(market: str, reporter: str | None) -> None:
    assert tariffs.reporter_for(market) == reporter


async def test_wits_fetch_keeps_each_partners_newest_rate() -> None:
    fake = Source()
    async with fake.client() as client:
        data = await tariffs.fetch(client, "918", TOWELS)
    # MFN history, then three years of all partners and the EU's three scheme groups.
    assert len(fake.calls) == 1 + tariffs.PREF_LOOKBACK_YEARS + 3
    rows = {(r["partner"], r["kind"]): r for r in data["rows"]}
    assert rows[("000", "MFN")]["year"] == 2023
    assert rows[("B29", "PREF")]["year"] == 2017 and rows[("B29", "PREF")]["rate"] == 0.0
    assert data["source"] == "wits" and "/reporter/918/" in data["url"]


async def test_uk_fetch_reads_every_preference() -> None:
    async with Source().client() as client:
        data = await tariffs.fetch(client, "826", TOWELS)
    rows = {r["partner"]: r for r in data["rows"]}
    assert data["source"] == "uk" and data["url"].endswith("/commodities/6302600010")
    # 12% for everyone; a 0% suspension for ships' stores (end use) doesn't count.
    assert rows["000"]["rate"] == 12.0 and rows["000"]["lines"] == 2
    assert (
        rows["PAK"]["scheme"] == "Developing Countries Trading Scheme (DCTS) - Enhanced Preferences"
    )
    assert rows["BGD"]["rate"] == 0.0 and rows["NLD"]["scheme"] == "European Union"
    assert rows["IND"]["rate"] == 0.0 and rows["IND"]["scheme"] is None  # its own agreement
    assert "CHN" not in rows and "BLR" not in rows  # no preference; extra duties left out


# ---------- duties ----------
async def test_requires_sign_in(client: AsyncClient) -> None:
    assert (await client.get(url("DEU"))).status_code == 401
    assert (await client.get(url("DEU", "landed-cost"))).status_code == 401


async def test_exporter_preference_against_rivals(
    user: AsyncClient, markets: None, source: Source
) -> None:
    response = await user.get(url("DEU"))
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"].startswith("private")
    body = response.json()
    assert body["yours"] == {
        "country": {"code": "PAK", "name": "Pakistan"}, "rate_pct": 0.0, "kind": "preference",
        "scheme": "EU GSP+", "year": 2017, "source": "WITS-TRAINS (World Bank, UNCTAD)",
        "note": "Last recorded in 2017; it may have changed since.",
    }  # fmt: skip
    assert body["standard"] == {"rate_pct": 12.0, "year": 2023, "source": body["yours"]["source"]}
    rivals = {r["country"]["code"]: r for r in body["rivals"]}
    assert list(rivals) == ["CHN", "TUR", "NLD"]  # largest first, Pakistan itself left out
    china = rivals["CHN"]
    assert (china["rate_pct"], china["kind"], china["advantage_pts"]) == (12.0, "standard", 12.0)
    assert china["note"] == landed_cost.MAY_APPLY  # no preference in the data: say so
    assert (rivals["TUR"]["rate_pct"], rivals["TUR"]["year"]) == (0.0, 2021)
    assert rivals["NLD"]["scheme"] == "EU single market" and rivals["NLD"]["rate_pct"] == 0.0
    assert body["main_rival"]["code"] == "CHN" and body["advantage_pts"] == 12.0
    assert body["summary"] == (
        "Germany charges Pakistan 0% on towels (EU GSP+, 2017) and China 12% "
        "(standard rate, 2023): a 12-point duty advantage for Pakistan."
    )
    assert body["stale"] is False and landed_cost.NOT_INCLUDED in body["notes"]


async def test_no_confirmed_preference_means_standard_rate(
    user: AsyncClient, markets: None, source: Source
) -> None:
    body = (await user.get(url("DEU", exporter="BGD"))).json()
    # Bangladesh's EBA group (B12) has no towel rows in the recording: no claim is made.
    assert body["yours"]["kind"] == "standard" and body["yours"]["rate_pct"] == 12.0
    assert body["yours"]["note"] == landed_cost.MAY_APPLY
    assert body["advantage_pts"] == 0.0 and "no duty advantage" in body["summary"]


async def test_uk_rates_are_live_and_complete(
    user: AsyncClient, markets: None, source: Source
) -> None:
    body = (await user.get(url("GBR"))).json()
    assert body["yours"]["scheme"].startswith("Developing Countries Trading Scheme")
    assert body["yours"]["year"] == datetime.now(UTC).year and body["yours"]["note"] is None
    china = body["rivals"][0]
    assert china["kind"] == "standard" and china["note"] is None  # the UK lists every preference
    assert body["source_url"].startswith("https://www.trade-tariff.service.gov.uk/")


async def test_us_rates_carry_the_extra_tariffs_note(
    user: AsyncClient, markets: None, source: Source
) -> None:
    body = (await user.get(url("USA"))).json()
    assert body["yours"]["rate_pct"] == 9.1 and body["yours"]["kind"] == "standard"
    assert body["notes"][0] == landed_cost.US_EXTRA


async def test_cached_then_stale_then_unavailable(
    user: AsyncClient,
    markets: None,
    source: Source,
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    await user.get(url("DEU"))
    first = len(source.calls)
    await user.get(url("FRA"))  # another EU member: same tariff, same cached row
    assert len(source.calls) == first

    async with db_sessionmaker() as s:  # age the copy past its refresh time
        old = datetime.now(UTC) - timedelta(days=Settings(_env_file=None).tariff_cache_days + 1)  # type: ignore[call-arg]
        await s.execute(update(TariffCache).values(fetched_at=old))
        await s.commit()
    source.handler = down
    stale = await user.get(url("DEU"))
    assert stale.status_code == 200 and stale.json()["stale"] is True

    unavailable = await user.get(url("USA"))  # nothing cached for the US
    assert unavailable.status_code == 503 and "isn't responding" in unavailable.json()["detail"]


async def test_no_duty_data_is_not_found_and_cached(
    user: AsyncClient, markets: None, source: Source
) -> None:
    for _ in range(2):
        response = await user.get(url("THA"))  # WITS has no towel rates for Thailand here
        assert response.status_code == 404 and "No percentage import duty" in response.text
    assert len(source.calls) == 1  # the empty answer was cached too


async def test_validation(user: AsyncClient, markets: None, source: Source) -> None:
    assert (await user.get(url("deu"))).status_code == 422
    assert (await user.get(url("DEU", hs6="6302"))).status_code == 422
    assert (await user.get(url("DEU", exporter="pak"))).status_code == 422
    both = url("DEU", "landed-cost", freight_pct=5, freight_usd_kg=0.2)
    assert (await user.get(both)).status_code == 422
    assert (await user.get(url("DEU", "landed-cost", cost_usd_kg=0))).status_code == 422
    assert (await user.get(url("DEU", exporter="CHN"))).status_code == 404  # not an exporter
    assert (await user.get(url("XXX"))).status_code == 404
    assert (await user.get(url("PAK"))).status_code == 404  # own country
    assert source.calls == []


# ---------- landed cost ----------
def test_landed_line_cif_and_fob() -> None:
    china = CountryOut(code="CHN", name="China")
    freight = landed_cost.Freight(pct=10)
    cif = landed_cost.landed_line(china, 4.0, 12.0, freight, fob_valuation=False)
    assert cif.freight_usd_kg == pytest.approx(0.4)
    assert cif.duty_usd_kg == pytest.approx(0.528)  # 12% of 4.40 (goods + freight)
    assert cif.landed_usd_kg == pytest.approx(4.928)
    fob = landed_cost.landed_line(china, 4.0, 12.0, freight, fob_valuation=True)
    assert fob.duty_usd_kg == pytest.approx(0.48)  # 12% of the goods only
    per_kg = landed_cost.landed_line(
        china, 4.0, 10.0, landed_cost.Freight(usd_kg=0.5), fob_valuation=False
    )
    assert per_kg.landed_usd_kg == pytest.approx(4.95)
    bare = landed_cost.landed_line(china, 4.0, 10.0, landed_cost.Freight(), fob_valuation=False)
    assert bare.freight_usd_kg == 0 and bare.landed_usd_kg == pytest.approx(4.4)


async def test_landed_cost_in_a_cif_market(
    user: AsyncClient, markets: None, source: Source
) -> None:
    response = await user.get(url("DEU", "landed-cost", cost_usd_kg=3, freight_pct=10))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["duty_base"] == "CIF" and body["freight_pct"] == 10
    assert body["yours"]["landed_usd_kg"] == pytest.approx(3.3)  # 3.00 + 0.30, no duty
    china = body["rivals"][0]
    assert china["fob_usd_kg"] == 4.2 and china["landed_usd_kg"] == pytest.approx(5.1744)
    assert [r["country"]["code"] for r in body["rivals"]] == ["CHN", "TUR", "NLD"]
    assert body["market_price_usd_kg"] == 4.0 and body["margin"] == pytest.approx(0.25)
    assert body["tone"] == "positive" and body["price_year"] == 2024
    assert body["explanation"][0] == body["duties"]["summary"]
    assert body["explanation"][1] == (
        "Landed cost in Germany, with 10% freight: yours $3.30/kg (from $3.00/kg, 0% duty); "
        "China's $5.17/kg (from $4.20/kg, 12% duty)."
    )
    assert body["explanation"][2].startswith("Your cost is 25% below what Germany pays")
    assert landed_cost.NO_FREIGHT not in body["notes"]


async def test_landed_cost_in_a_fob_market_without_your_cost(
    user: AsyncClient, markets: None, source: Source
) -> None:
    body = (await user.get(url("USA", "landed-cost", freight_usd_kg=0.5))).json()
    assert body["duty_base"] == "FOB" and body["yours"] is None and body["margin"] is None
    china = body["rivals"][0]  # 9.1% of the $4.00 goods only; freight isn't dutiable
    assert china["duty_usd_kg"] == pytest.approx(0.364)
    assert china["landed_usd_kg"] == pytest.approx(4.864)
    assert len(body["explanation"]) == 2 and body["verdict"] is None


async def test_landed_cost_without_freight_says_so(
    user: AsyncClient, markets: None, source: Source
) -> None:
    body = (await user.get(url("DEU", "landed-cost", cost_usd_kg=3))).json()
    assert "before freight" in body["explanation"][1]
    assert body["notes"][-1] == landed_cost.NO_FREIGHT


# ---------- the guide ----------
@dataclass
class Script:
    replies: list[AIMessage] = field(default_factory=list)
    inputs: list[list[BaseMessage]] = field(default_factory=list)


@pytest.fixture
def script(
    monkeypatch: pytest.MonkeyPatch,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    source: Source,
) -> Script:
    """A scripted model (no tokens spent); the guide reaches the fake sources."""
    s = Script()

    def fake_model(spec: CallSpec, settings: Any = None) -> Any:
        async def answer(messages: list[BaseMessage]) -> AIMessage:
            s.inputs.append(messages)
            return s.replies.pop(0)

        return RunnableLambda(lambda _: None, afunc=answer)

    monkeypatch.setattr(chat_service.llm, "get_chat_model", fake_model)
    monkeypatch.setattr(tasks, "session_factory", db_sessionmaker)
    client = source.client()
    monkeypatch.setattr(chat_service, "http_client", lambda: client)
    return s


async def test_guide_checks_duties(user: AsyncClient, markets: None, script: Script) -> None:
    profile = {"exporter": "PAK", "role": "exporter", "products": [TOWELS], "current_markets": []}
    assert (await user.put("/api/v1/me/profile", json=profile)).status_code == 200
    call = {
        "name": "duty_check",
        "args": {"product": TOWELS, "market": "Germany"},
        "id": uuid.uuid4().hex,
    }
    script.replies = [
        AIMessage(content="", tool_calls=[call]),
        AIMessage("Germany charges you 0% (EU GSP+, 2017) and China 12%: a 12-point advantage."),
    ]
    response = await user.post("/api/v1/chat/messages", json={"text": "Duty on towels in Germany?"})
    events = [
        json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
    ]
    assert [e["event"] for e in events] == ["thread", "status", "card", "answer", "done"]
    assert events[1]["text"] == "Checking import duties"
    card = events[2]["card"]
    assert card["type"] == "duty" and card["yours"]["scheme"] == "EU GSP+"
    assert card["advantage_pts"] == 12.0 and card["rivals"][0]["country"]["code"] == "CHN"
    assert events[3]["grounded"] is True
    facts = script.inputs[1][-1].content
    assert "Pakistan: 0% (EU GSP+, 2017)" in facts and "Standard (MFN) rate: 12% (2023)" in facts


async def _context(
    db_sessionmaker: async_sessionmaker[AsyncSession], client: httpx.AsyncClient
) -> tools.ChatContext:
    return tools.ChatContext(
        db=db_sessionmaker(), http=client, settings=Settings(_env_file=None),  # type: ignore[call-arg]
        exporter=CountryOut(code="PAK", name="Pakistan"), goal="sell", products=[],
        current_markets=frozenset(),
    )  # fmt: skip


PRICE_ARGS = {
    "product": TOWELS, "market": "DEU", "stock_value": "15000", "currency": "USD",
    "quantity": "5000 kg",
}  # fmt: skip


async def test_price_check_mentions_the_duty(
    markets: None, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    async with Source().client() as client:
        ctx = await _context(db_sessionmaker, client)
        outcome = await tools.run_tool(ctx, "price_check", PRICE_ARGS)
        await ctx.db.close()
    assert outcome.result is not None
    assert (
        "Import duty: Germany charges Pakistan 0% on towels (EU GSP+, 2017)" in outcome.result.text
    )


async def test_price_check_works_without_duties(
    markets: None, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    async with Source(handler=down).client() as client:
        ctx = await _context(db_sessionmaker, client)
        price = await tools.run_tool(ctx, "price_check", PRICE_ARGS)
        duty = await tools.run_tool(ctx, "duty_check", {"product": TOWELS, "market": "DEU"})
        await ctx.db.close()
    assert price.result is not None and "Import duty" not in price.result.text
    assert price.result.text.startswith("Stock worth 15,000 USD")
    assert duty.error == "The tariff data source isn't responding"
