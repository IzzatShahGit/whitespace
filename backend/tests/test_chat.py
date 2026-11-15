"""The Whitespace guide: tool use, cards, grounding, limits, privacy, failures.

The model is scripted (no tokens spent): each test lists the replies it will give.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from httpx import AsyncClient
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.runnables import RunnableLambda
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.seed import TOWELS
from whitespace_api.agents.chat.amounts import parse_amount, parse_kg
from whitespace_api.agents.chat.graph import FREE_INTEGERS, unsupported_figures
from whitespace_api.agents.llm import CallSpec
from whitespace_api.core import tasks
from whitespace_api.core.config import Settings, get_settings
from whitespace_api.main import app
from whitespace_api.models import ChatMessage, ChatThread
from whitespace_api.services import chat as chat_service
from whitespace_api.services.pricing import check_price

PROFILE = {"exporter": "PAK", "role": "exporter", "products": [TOWELS], "current_markets": []}


def call(name: str, **args: Any) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": uuid.uuid4().hex}])


@dataclass
class Script:
    """Replies the fake model gives in order, and what it was asked."""

    replies: list[AIMessage | Exception] = field(default_factory=list)
    specs: list[CallSpec] = field(default_factory=list)
    inputs: list[list[BaseMessage]] = field(default_factory=list)


@pytest.fixture
def script(
    monkeypatch: pytest.MonkeyPatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> Iterator[Script]:
    s = Script()

    def fake_get_chat_model(spec: CallSpec, settings: Any = None) -> Any:
        async def answer(messages: list[BaseMessage]) -> AIMessage:
            s.specs.append(spec)
            s.inputs.append(messages)
            reply = s.replies.pop(0)
            if isinstance(reply, Exception):
                raise reply
            return reply

        return RunnableLambda(lambda _: None, afunc=answer)

    monkeypatch.setattr(chat_service.llm, "get_chat_model", fake_get_chat_model)
    monkeypatch.setattr(tasks, "session_factory", db_sessionmaker)
    yield s


def events(body: str) -> list[dict[str, Any]]:
    return [
        json.loads(line.removeprefix("data: "))
        for chunk in body.split("\n\n")
        for line in chunk.splitlines()
        if line.startswith("data: ")
    ]


async def ask(user: AsyncClient, text: str, thread_id: str | None = None) -> list[dict[str, Any]]:
    response = await user.post("/api/v1/chat/messages", json={"text": text, "thread_id": thread_id})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    return events(response.text)


@pytest.fixture
async def seller(user: AsyncClient) -> AsyncClient:
    assert (await user.put("/api/v1/me/profile", json=PROFILE)).status_code == 200
    return user


async def test_requires_sign_in(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/chat/threads")).status_code == 401
    assert (await client.post("/api/v1/chat/messages", json={"text": "hi"})).status_code == 401
    assert (await client.get("/api/v1/chat/suggestions")).status_code == 401


async def test_reply_uses_data_and_shows_cards(seller: AsyncClient, script: Script) -> None:
    script.replies = [
        call("best_markets", product=TOWELS),
        AIMessage("Thailand is your best bet: imports of $164M, growing 19% a year."),
    ]
    got = await ask(seller, "Where should I sell towels?")
    kinds = [e["event"] for e in got]
    assert kinds == ["thread", "status", "card", "answer", "done"]
    assert got[1]["text"] == "Ranking markets"
    card = got[2]["card"]
    assert card["type"] == "markets" and card["items"][0]["market"]["code"] == "THA"
    answer = got[3]
    assert answer["grounded"] is True
    assert "Tell me more about Thailand" in answer["follow_ups"]
    # The model never chose the exporter: the tool used the profile's country.
    tool_reply = script.inputs[1][-1]
    assert isinstance(tool_reply, ToolMessage) and "from Pakistan" in tool_reply.content

    thread = (await seller.get(f"/api/v1/chat/threads/{got[0]['thread_id']}")).json()
    assert thread["title"] == "Where should I sell towels?"
    question, reply = thread["messages"]
    assert question["role"] == "user" and reply["status"] == "done"
    assert reply["cards"][0]["type"] == "markets" and reply["grounded"] is True


async def test_invented_figures_are_repaired(seller: AsyncClient, script: Script) -> None:
    script.replies = [
        call("best_markets", product=TOWELS),
        AIMessage("Thailand imports $999M a year."),  # not in the data
        AIMessage("Thailand imports $164M a year."),
    ]
    answer = next(e for e in await ask(seller, "Best market?") if e["event"] == "answer")
    assert answer["text"] == "Thailand imports $164M a year." and answer["grounded"] is True
    assert script.specs[-1].tools == ()  # the repair can't call tools
    assert "999" in script.inputs[-1][-1].content


async def test_figures_still_unsupported_are_flagged(seller: AsyncClient, script: Script) -> None:
    script.replies = [
        call("best_markets", product=TOWELS),
        AIMessage("Thailand imports $999M."),
        AIMessage("Thailand imports $998M."),
    ]
    answer = next(e for e in await ask(seller, "Best market?") if e["event"] == "answer")
    assert answer["grounded"] is False


async def test_the_last_round_must_answer(seller: AsyncClient, script: Script) -> None:
    script.replies = [call("best_markets", product=TOWELS) for _ in range(3)] + [
        AIMessage("Here is what I found.")
    ]
    await ask(seller, "Best market?")
    assert [bool(s.tools) for s in script.specs] == [True, True, True, False]


async def test_tool_problems_go_back_to_the_model(seller: AsyncClient, script: Script) -> None:
    script.replies = [
        call("market_facts", product=TOWELS, market="Atlantis"),
        AIMessage("I don't know that country. Which market do you mean?"),
    ]
    got = await ask(seller, "How is Atlantis?")
    error = script.inputs[1][-1]
    assert isinstance(error, ToolMessage) and error.content.startswith("Error: Unknown country")
    assert [e["event"] for e in got] == ["thread", "status", "answer", "done"]


async def test_follow_ups_resolve_from_the_memo(seller: AsyncClient, script: Script) -> None:
    script.replies = [call("best_markets", product=TOWELS), AIMessage("Thailand leads.")]
    first = await ask(seller, "Where to sell towels?")
    script.replies = [AIMessage("The second one is Germany.")]
    await ask(seller, "And the second one?", thread_id=first[0]["thread_id"])
    history = script.inputs[-1]
    remembered = next(m for m in history if isinstance(m, AIMessage))
    assert (
        f"[Context: product {TOWELS}" in remembered.content
        and "THA, DEU, USA" in remembered.content
    )


async def test_price_check_converts_local_money(
    seller: AsyncClient, script: Script, monkeypatch: pytest.MonkeyPatch
) -> None:
    from whitespace_api.integrations import fx

    monkeypatch.setattr(
        fx, "_cache", fx.Rates(per_usd={"PKR": 280.0}, updated="today", fetched_at=9e18)
    )
    script.replies = [
        call("price_check", product=TOWELS, market="Germany", stock_value="18 lakh",
             currency="PKR", quantity="5 tons"),
        AIMessage("Your 18 lakh is about $6,429, so $1.29/kg."),
    ]  # fmt: skip
    got = await ask(seller, "I have 18 lakh of towels, 5 tons. Can I compete in Germany?")
    card = next(e["card"] for e in got if e["event"] == "card")
    assert card["type"] == "price" and card["stock_value"] == 1_800_000
    assert card["quantity_kg"] == 5000 and round(card["cost_usd_kg"], 2) == 1.29
    assert next(e for e in got if e["event"] == "answer")["grounded"] is True


async def test_one_reply_at_a_time(
    seller: AsyncClient, script: Script, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    script.replies = [AIMessage("Hello!")]
    thread_id = (await ask(seller, "Hi"))[0]["thread_id"]
    async with db_sessionmaker() as db:
        db.add(ChatMessage(thread_id=uuid.UUID(thread_id), role="assistant", status="pending"))
        await db.commit()
    busy = await seller.post(
        "/api/v1/chat/messages", json={"text": "Again", "thread_id": thread_id}
    )
    assert busy.status_code == 409


async def test_daily_limit_is_atomic_and_charges_nothing_extra(
    seller: AsyncClient, script: Script, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, chat_daily_limit=1)  # type: ignore[call-arg]
    script.replies = [AIMessage("Hello!")]
    await ask(seller, "Hi")
    blocked = await seller.post("/api/v1/chat/messages", json={"text": "Again"})
    assert blocked.status_code == 429
    async with db_sessionmaker() as db:  # the blocked turn left nothing behind
        assert len((await db.scalars(select(ChatThread))).all()) == 1
        assert len((await db.scalars(select(ChatMessage))).all()) == 2
    suggestions = (await seller.get("/api/v1/chat/suggestions")).json()
    assert suggestions["remaining_today"] == 0


async def test_conversations_are_private(
    seller: AsyncClient, script: Script, client: AsyncClient
) -> None:
    script.replies = [AIMessage("Hello!")]
    thread_id = (await ask(seller, "Hi"))[0]["thread_id"]
    # Same client, new identity: register another user (cookies switch to them).
    await client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "full_name": "Other", "password": "towels-2026!"},
    )
    assert (await client.get(f"/api/v1/chat/threads/{thread_id}")).status_code == 404
    assert (await client.delete(f"/api/v1/chat/threads/{thread_id}")).status_code == 404
    reply = await client.post("/api/v1/chat/messages", json={"text": "x", "thread_id": thread_id})
    assert reply.status_code == 404
    assert (await client.get("/api/v1/chat/threads")).json() == []


async def test_delete_and_list(seller: AsyncClient, script: Script) -> None:
    script.replies = [AIMessage("One"), AIMessage("Two")]
    first = (await ask(seller, "First question"))[0]["thread_id"]
    await ask(seller, "Second question")
    titles = [t["title"] for t in (await seller.get("/api/v1/chat/threads")).json()]
    assert titles == ["Second question", "First question"]  # most recent first
    assert (await seller.delete(f"/api/v1/chat/threads/{first}")).status_code == 204
    assert (await seller.get(f"/api/v1/chat/threads/{first}")).status_code == 404


async def test_failure_is_saved_and_reported(seller: AsyncClient, script: Script) -> None:
    script.replies = [RuntimeError("provider down")]
    got = await ask(seller, "Hi")
    assert [e["event"] for e in got] == ["thread", "error", "done"]
    thread = (await seller.get(f"/api/v1/chat/threads/{got[0]['thread_id']}")).json()
    assert thread["messages"][1]["status"] == "failed"
    assert "provider" not in thread["messages"][1]["content"]  # no internals leak


async def test_validation(seller: AsyncClient) -> None:
    assert (await seller.post("/api/v1/chat/messages", json={"text": "   "})).status_code == 422
    too_long = {"text": "x" * 1501}
    assert (await seller.post("/api/v1/chat/messages", json=too_long)).status_code == 422
    missing = {"text": "hi", "thread_id": str(uuid.uuid4())}
    assert (await seller.post("/api/v1/chat/messages", json=missing)).status_code == 404


async def test_suggestions_are_personal(seller: AsyncClient) -> None:
    body = (await seller.get("/api/v1/chat/suggestions")).json()
    assert body["prompts"][0] == "Where should I sell my towels next?"
    assert any("Thailand" in p for p in body["prompts"])
    assert body["remaining_today"] == Settings(_env_file=None).chat_daily_limit  # type: ignore[call-arg]


# ---------- pure functions ----------
def test_unsupported_figures() -> None:
    sources = ["Imports $164M, growth +19%/yr; pays $4.10/kg"]
    assert unsupported_figures("Imports $164M growing 19%, about $4.1/kg", sources) == []
    assert unsupported_figures("Imports $165M", sources) == ["165"]
    assert unsupported_figures(f"Take {FREE_INTEGERS} steps", sources) == []


@pytest.mark.parametrize(
    ("text", "value"),
    [("18 lakh", 1.8e6), ("2.5 crore", 2.5e7), ("1,250,000", 1.25e6), ("500k", 5e5), ("abc", None),
     ("0", None), ("3 apples", None)],
)  # fmt: skip
def test_parse_amount(text: str, value: float | None) -> None:
    assert parse_amount(text) == value


def test_parse_kg() -> None:
    assert parse_kg("5 tons") == 5000 and parse_kg("800kg") == 800 and parse_kg("2 bags") is None


def test_check_price() -> None:
    cheap = check_price(value_usd=6000, quantity_kg=5000, market_price=4.0, market="Germany")
    assert cheap.tone == "positive" and cheap.cost_usd_kg == 1.2 and cheap.revenue_usd == 20000
    dear = check_price(value_usd=25000, quantity_kg=5000, market_price=4.0, market="Germany")
    assert dear.tone == "negative"
    no_qty = check_price(value_usd=6000, quantity_kg=None, market_price=4.0, market="Germany")
    assert no_qty.cost_usd_kg is None and no_qty.verdict is None
