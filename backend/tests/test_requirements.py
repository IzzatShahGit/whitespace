"""Import requirements: the quote check, the research flow, the API, the checklist."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.seed import TOWELS
from whitespace_api.agents import requirements as agent
from whitespace_api.agents.leads import _norm
from whitespace_api.agents.llm import CallSpec
from whitespace_api.core import tasks
from whitespace_api.core.config import Settings, get_settings
from whitespace_api.main import app
from whitespace_api.repositories import requirements as repo
from whitespace_api.schemas.requirements import RequirementSource
from whitespace_api.services import requirements as service

RAW = AIMessage(
    content="",
    usage_metadata={"input_tokens": 900, "output_tokens": 200, "total_tokens": 1100},
    response_metadata={"model_name": "fake"},
)
PAGE = (
    "Germany - Import Requirements and Documentation. Textile products placed on the EU "
    "market must carry a label stating the fibre composition, in accordance with "
    "Regulation (EU) No 1007/2011. A commercial invoice and packing list are required for "
    "all shipments. Exporters from GSP+ countries need a REX statement on origin."
)
SOURCES = [
    RequirementSource(
        id="S1", title="Germany import requirements", url="https://www.trade.gov/de",
        domain="trade.gov", official=True,
    ),
    RequirementSource(
        id="S2", title="Blog", url="https://blog.example/x", domain="blog.example",
        official=False,
    ),
]  # fmt: skip
TEXTS = {"S1": PAGE, "S2": "Nothing useful here at all."}


def item(title: str, quote: str, source: str = "S1", need: str = "required") -> agent.FoundItem:
    return agent.FoundItem(
        category="labelling", title=title, detail="What it is.", need=need,  # type: ignore[arg-type]
        quote=quote, source=source,
    )  # fmt: skip


def test_quotes_must_be_on_the_page() -> None:
    page = _norm(PAGE)
    exact = "must carry a label stating the fibre composition"
    assert agent.quote_on_page(exact, page)
    assert agent.quote_on_page("Must carry a label, stating the FIBRE composition!", page)
    assert agent.quote_on_page("must carry label stating the fibre composition", page)  # 1 gap
    assert not agent.quote_on_page("must carry a label stating the country of origin", page)
    assert not agent.quote_on_page("fibre composition", page)  # too short to prove anything
    assert not agent.quote_on_page("labels must state fibre content clearly", page)  # paraphrase


def test_check_keeps_backed_items_official_and_required_first() -> None:
    found = [
        item("Origin statement (REX)", "Exporters from GSP+ countries need a REX statement",
             need="depends"),
        item("Fibre composition label", "must carry a label stating the fibre composition"),
        item("Invented rule", "all towels must be pink and certified by the moon", "S1"),
        item("Wrong page", "must carry a label stating the fibre composition", "S2"),
        item("Fibre  composition LABEL", "must carry a label stating the fibre composition"),
        item("Ghost page", "must carry a label stating the fibre composition", "S9"),
    ]  # fmt: skip
    content = agent.check(found, SOURCES, TEXTS)
    assert [i.title for i in content.items] == ["Fibre composition label", "Origin statement (REX)"]
    assert content.removed == 3  # invented, wrong page, unknown page (duplicate isn't "removed")
    assert [s.id for s in content.sources] == ["S1"]
    assert content.items[0].key == agent.item_key("fibre composition label")


def test_official_sites() -> None:
    assert agent.is_official("www.trade.gov", "DEU")
    assert agent.is_official("trade.ec.europa.eu", "FRA")
    assert not agent.is_official("trade.ec.europa.eu", "USA")  # not the US's rules
    assert agent.is_official("www.cbp.gov", "USA") and agent.is_official("www.gov.uk", "USA")
    assert agent.is_official("www.zoll.gouv.fr", "FRA") and agent.is_official("x.go.jp", "JPN")
    assert not agent.is_official("go.example.com", "USA")
    assert not agent.is_official("governance-blog.com", "USA")


async def test_find_requirements_runs_official_searches_and_checks() -> None:
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        bodies.append(body)
        if request.url.path == "/extract":
            return httpx.Response(
                200, json={"results": [{"url": u, "raw_content": PAGE} for u in body["urls"]]}
            )
        return httpx.Response(200, json={"results": [
            {"title": "Germany import requirements", "url": "https://www.trade.gov/de",
             "content": "Import requirements"},
            {"title": "A blog", "url": "https://blog.example/x", "content": "towels"},
        ]})  # fmt: skip

    found = agent.Found(
        items=[
            item("Fibre label", "must carry a label stating the fibre composition"),
            item("Invoice", "A commercial invoice and packing list are required for all shipments"),
        ]
    )

    def chat(spec: CallSpec) -> Any:
        parsed = agent.Duplicates(groups=[[1, 2]]) if spec.schema is agent.Duplicates else found
        return RunnableLambda(lambda _: {"raw": RAW, "parsed": parsed})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        deps = agent.RequirementsDeps(http=http, search_key="k", chat=chat)
        run = await agent.find_requirements(
            deps, product="towels", detail=None, market="Germany", market_code="DEU",
            exporter="Pakistan", scheme="EU GSP+",
        )  # fmt: skip
    searches = [b for b in bodies if "query" in b]
    assert len(searches) == 6 and searches[0]["include_domains"] == ["trade.gov"]
    assert "European Union" in searches[1]["query"]  # EU rules are searched EU-wide
    assert "europa.eu" in searches[1]["include_domains"]
    assert searches[3]["query"].startswith("EU GSP+ proof of origin")  # the lane's scheme
    assert "include_domains" not in searches[5]
    assert run.content.sources[0].official and run.pages_read == 2
    # The model grouped items 1 and 2 as one: only the first is kept.
    assert [i.title for i in run.content.items] == ["Fibre label"]


async def test_no_search_key_spends_nothing() -> None:
    async with httpx.AsyncClient() as http:
        deps = agent.RequirementsDeps(http=http, search_key=None, chat=lambda s: None)  # type: ignore[arg-type,return-value]
        run = await agent.find_requirements(
            deps, product="towels", detail=None, market="Germany", market_code="DEU",
            exporter="Pakistan",
        )  # fmt: skip
    assert run.content.research_available is False and run.calls == []


# --- API ----------------------------------------------------------------------------

URL = f"/api/v1/markets/DEU/requirements?hs6={TOWELS}&exporter=PAK"


@pytest.fixture
def research(
    monkeypatch: pytest.MonkeyPatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> Iterator[list[str]]:
    calls: list[str] = []

    async def fake_find(deps: Any, *, product: str, market: str, exporter: str, **_: Any) -> Any:
        calls.append(f"{product}|{market}|{exporter}")
        content = agent.check(
            [item("Fibre label", "must carry a label stating the fibre composition")],
            SOURCES, TEXTS,
        )  # fmt: skip
        return agent.RequirementsRun(content=content, searches=4, pages_read=1, calls=[])

    monkeypatch.setattr(service, "find_requirements", fake_find)
    monkeypatch.setattr(tasks, "session_factory", db_sessionmaker)
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,  # type: ignore[call-arg]
        tavily_api_key="test",  # type: ignore[arg-type]
        requirements_daily_limit=2,
    )
    yield calls
    app.dependency_overrides.pop(get_settings, None)


async def test_lifecycle_cache_and_checklist(user: AsyncClient, research: list[str]) -> None:
    assert (await user.get(URL)).json()["status"] == "missing"
    started = await user.post(URL)
    assert started.status_code == 202 and started.json()["status"] == "pending"
    await tasks.wait_for_jobs()
    ready = (await user.get(URL)).json()
    assert ready["status"] == "ready" and research == ["towels|Germany|Pakistan"]
    key = ready["content"]["items"][0]["key"]

    assert (await user.post(URL)).status_code == 200 and len(research) == 1  # cached

    tick = f"/api/v1/markets/DEU/requirements/done/{key}?hs6={TOWELS}"
    assert (await user.put(tick)).status_code == 204
    assert (await user.put(tick)).status_code == 204  # idempotent
    assert (await user.get(URL)).json()["done"] == [key]
    assert (await user.delete(tick)).status_code == 204
    assert (await user.get(URL)).json()["done"] == []
    assert (await user.put(tick.replace(key, "not-a-key"))).status_code == 422


async def test_limits_and_unknown_codes(user: AsyncClient, research: list[str]) -> None:
    assert (await user.post(URL.replace("DEU", "ZZZ"))).status_code == 404
    assert (await user.post(URL.replace("PAK", "DEU"))).status_code == 404  # same country
    for market in ("DEU", "USA"):
        assert (await user.post(URL.replace("DEU", market))).status_code == 202
        await tasks.wait_for_jobs()
    limited = await user.post(URL.replace("DEU", "THA"))
    assert limited.status_code == 429


async def test_a_superseded_run_cannot_overwrite(
    user: AsyncClient, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Run A is abandoned, run B takes over; A finishing late must not clobber B."""
    key = (TOWELS, "DEU", "PAK")
    me = (await user.get("/api/v1/auth/me")).json()["id"]
    async with db_sessionmaker() as db:
        a = await repo.claim(db, key, user_id=uuid.UUID(me), abandoned_after=timedelta(hours=1))
        assert a is not None
        assert (
            await repo.claim(db, key, user_id=uuid.UUID(me), abandoned_after=timedelta(hours=1))
            is None
        )
        b = await repo.claim(db, key, user_id=uuid.UUID(me), abandoned_after=timedelta(seconds=-1))
        assert b is not None and b != a
        assert await repo.finish(db, key, b, status="ready", content={"items": []}) is True
        assert await repo.finish(db, key, a, status="failed", error="late") is False
        row = await repo.get(db, key)
        assert row is not None and row.status == "ready" and row.error is None
