"""Company leads: the grounding check, the search flow, and the API lifecycle."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.seed import TOWELS
from whitespace_api.agents import leads as agent
from whitespace_api.agents.llm import CallSpec
from whitespace_api.core import tasks
from whitespace_api.core.config import Settings, get_settings
from whitespace_api.main import app
from whitespace_api.schemas.lead import LeadsContent, LeadSource
from whitespace_api.services import leads as service

RAW = AIMessage(
    content="",
    usage_metadata={"input_tokens": 900, "output_tokens": 200, "total_tokens": 1100},
    response_metadata={"model_name": "fake"},
)

PAGE = (
    "Towel importers in Germany: Hansen Textil GmbH & Co. KG, Hamburg (www.hansen-textil.de). "
    "Frottana Vertrieb, Berlin. Listed on Europages. Heimtextil 2027, Frankfurt, 12-15 January."
)
SOURCES = [
    LeadSource(id="S1", title="Importers", url="https://dir.example/list", domain="dir.example")
]
TEXTS = {"S1": PAGE}


def company(name: str, **extra: Any) -> agent.FoundCompany:
    fields: dict[str, Any] = {"kind": "importer", "handles": "towels", "source": "S1"} | extra
    return agent.FoundCompany(name=name, **fields)


def test_check_keeps_only_names_on_the_cited_page() -> None:
    found = agent.Found(
        companies=[
            company("Hansen Textil GmbH & Co. KG", website="hansen-textil.de", city="Hamburg"),
            company("Hansen Textil"),  # duplicate of the first
            company("Frottana Vertrieb", website="https://frottana.com"),  # site not on page
            company("Made-Up Towels AG"),  # invented: not on the page
            company("Europages"),  # a directory, not a company
            company("Hansen Textil", source="S9"),  # unknown source
        ],
        events=[
            agent.FoundEvent(name="Heimtextil 2027", city="Frankfurt", source="S1"),
            agent.FoundEvent(name="Towel Expo", source="S1"),  # not on the page
        ],
    )
    content = agent.check(found, SOURCES, TEXTS)

    assert [c.name for c in content.companies] == [
        "Hansen Textil GmbH & Co. KG",
        "Frottana Vertrieb",
    ]
    assert content.companies[0].website == "https://hansen-textil.de"
    assert content.companies[1].website is None
    assert [e.name for e in content.events] == ["Heimtextil 2027"]
    assert content.removed == 3  # invented, directory and the unknown event; repeats are skipped


def test_accents_duplicates_and_people_data() -> None:
    page = "MÖVE Frottierwaren. Heimtextil 2027 Frankfurt. Heimtextil Frankfurt, January."
    found = agent.Found(
        companies=[company("MÖVE")],
        events=[
            agent.FoundEvent(name="Heimtextil 2027", source="S1"),
            agent.FoundEvent(name="Heimtextil Frankfurt", source="S1"),
        ],
    )
    content = agent.check(found, SOURCES, {"S1": page})
    assert [c.name for c in content.companies] == ["MÖVE"]
    assert [e.name for e in content.events] == ["Heimtextil 2027"]
    assert agent.plan_queries("towels", "Germany", "buyers", 2026, "Handtücher", "textile")[
        -2:
    ] == ["Handtücher", "towels textile trade fair Germany 2026 exhibitors"]


def test_batches_keep_each_call_small() -> None:
    sources = [
        LeadSource(id=f"S{i}", title="t", url=f"https://x{i}.example", domain="x.example")
        for i in range(1, 5)
    ]
    texts = {"S1": "a" * 7000, "S2": "b" * 3000, "S3": "c" * 400, "S4": "d" * 9000}
    groups = agent.batches(sources, texts)
    assert [[s.id for s in g] for g in groups] == [["S1"], ["S2", "S3"], ["S4"]]


def test_core_name_strips_only_trailing_legal_words() -> None:
    assert agent.core_name("The Hansen Textil GmbH & Co. KG") == "hansen textil"
    assert agent.core_name("Co-op Towels Ltd") == "co op towels"
    assert (
        agent.core_name("M/s. Al-Karam Towel Industries (Pvt.) Ltd.") == "al karam towel industries"
    )
    assert agent.is_past("TEXPO 2024", None, 2026)
    assert not agent.is_past("Heimtextil", "January 2026 / 2027", 2026)
    assert not agent.on_page("Ltd", PAGE.lower())  # too short to prove anything


def fake_chat(found: agent.Found, local: str | None = "Handtücher Großhandel") -> Any:
    def factory(spec: CallSpec) -> RunnableLambda[Any, Any]:
        parsed = agent.LocalQuery(query=local) if spec.schema is agent.LocalQuery else found
        return RunnableLambda(lambda _: {"raw": RAW, "parsed": parsed})

    return factory


async def test_find_leads_searches_reads_list_pages_and_checks() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        if request.url.path == "/extract":
            urls = json.loads(request.content)["urls"]
            return httpx.Response(
                200, json={"results": [{"url": u, "raw_content": PAGE} for u in urls]}
            )
        result = {
            "title": "Towel importers list",
            "url": "https://dir.example/list",
            "content": "x",
        }
        return httpx.Response(200, json={"results": [result]})

    found = agent.Found(companies=[company("Hansen Textil GmbH"), company("Ghost Co")], events=[])
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        deps = agent.LeadsDeps(http=http, search_key="k", chat=fake_chat(found))
        run = await agent.find_leads(
            deps, product="towels", country="Germany", side="buyers", year=2026
        )

    assert requests.count("/search") == 5 and requests.count("/extract") == 1  # + local query
    assert run.searches == 5 and run.pages_read == 1
    assert len(run.calls) == 2  # local query + one extraction batch
    assert [c.name for c in run.content.companies] == ["Hansen Textil GmbH"]
    assert run.content.removed == 1


async def test_find_leads_without_search_key_spends_nothing() -> None:
    async with httpx.AsyncClient() as http:
        deps = agent.LeadsDeps(
            http=http, search_key=None, chat=fake_chat(agent.Found(companies=[], events=[]))
        )
        run = await agent.find_leads(
            deps, product="towels", country="Germany", side="buyers", year=2026
        )
    assert run.content.research_available is False and run.calls == []


# --- API --------------------------------------------------------------------------

URL = f"/api/v1/countries/DEU/leads?hs6={TOWELS}&side=buyers"


@pytest.fixture
def searches(
    monkeypatch: pytest.MonkeyPatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> Iterator[list[str]]:
    """Fake search agent and LLM; background jobs on the test database; limit of 2/day."""
    calls: list[str] = []

    async def fake_find(deps: Any, *, product: str, country: str, side: str, **_: Any) -> Any:
        calls.append(f"{product}|{country}|{side}")
        content = LeadsContent(
            companies=[
                agent.check(
                    agent.Found(companies=[company("Hansen Textil")], events=[]), SOURCES, TEXTS
                ).companies[0]
            ],
            events=[],
            sources=SOURCES,
            research_available=True,
            removed=0,
        )
        return agent.LeadsRun(content=content, searches=4, pages_read=1, calls=[agent._usage(RAW)])

    def fake_model(spec: CallSpec, settings: Any = None) -> Any:
        draft = service.IntroDraft(subject="Towels for Hansen", body="Dear Hansen team, ...")
        return RunnableLambda(lambda _: {"raw": RAW, "parsed": draft})

    monkeypatch.setattr(service, "find_leads", fake_find)
    monkeypatch.setattr(service.llm, "get_chat_model", fake_model)
    monkeypatch.setattr(tasks, "session_factory", db_sessionmaker)
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,  # type: ignore[call-arg]
        tavily_api_key="test",  # type: ignore[arg-type]
        leads_daily_limit=2,
        intro_daily_limit=1,
    )
    yield calls
    app.dependency_overrides.pop(get_settings, None)


async def test_leads_lifecycle_and_cache(user: AsyncClient, searches: list[str]) -> None:
    assert (await user.get(URL)).json()["status"] == "missing"
    assert searches == []  # opening a page never searches

    started = await user.post(URL)
    assert started.status_code == 202 and started.json()["status"] == "pending"
    await tasks.wait_for_jobs()

    ready = (await user.get(URL)).json()
    assert ready["status"] == "ready" and ready["side"] == "buyers"
    assert ready["content"]["companies"][0]["name"] == "Hansen Textil"
    assert ready["usage"]["searches"] == 4 and ready["usage"]["pages_read"] == 1
    assert searches == ["towels|Germany|buyers"]

    again = await user.post(URL)
    assert again.status_code == 200 and searches == ["towels|Germany|buyers"]  # cached


async def test_sides_are_separate_and_limited(user: AsyncClient, searches: list[str]) -> None:
    for side in ("buyers", "suppliers"):
        assert (await user.post(URL.replace("buyers", side))).status_code == 202
        await tasks.wait_for_jobs()
    limited = await user.post(f"/api/v1/countries/THA/leads?hs6={TOWELS}&side=buyers")
    assert limited.status_code == 429 and "limit" in limited.json()["detail"]


async def test_unknown_country_and_bad_side(user: AsyncClient, searches: list[str]) -> None:
    assert (await user.post(URL.replace("DEU", "ZZZ"))).status_code == 404
    assert (await user.get(URL.replace("buyers", "friends"))).status_code == 422


async def test_intro_draft_and_limit(user: AsyncClient, searches: list[str]) -> None:
    body = {"hs6": TOWELS, "country": "DEU", "side": "buyers", "company": "Hansen Textil"}
    first = await user.post("/api/v1/leads/intro", json=body)
    assert first.status_code == 200
    assert first.json() == {
        "subject": "Towels for Hansen",
        "body": "Dear Hansen team, ...",
        "drafted_by": "ai",
    }
    assert (await user.post("/api/v1/leads/intro", json=body)).status_code == 429


async def test_intro_falls_back_to_template(
    user: AsyncClient, searches: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(spec: CallSpec, settings: Any = None) -> Any:
        def fail(_: Any) -> Any:
            raise RuntimeError("quota")

        return RunnableLambda(fail)

    monkeypatch.setattr(service.llm, "get_chat_model", broken)
    body = {"hs6": TOWELS, "country": "DEU", "side": "suppliers", "company": "Hansen Textil"}
    out = (await user.post("/api/v1/leads/intro", json=body)).json()
    assert out["drafted_by"] == "template"
    assert "Dear Hansen Textil team" in out["body"] and "[Your name]" in out["body"]


async def test_requires_sign_in(client: AsyncClient) -> None:
    assert (await client.get(URL)).status_code == 401
