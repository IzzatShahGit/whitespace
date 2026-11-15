"""Brief lifecycle over the API: request, background generation, cache, limits, failures."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from httpx import AsyncClient
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.seed import BED_LINEN, TOWELS
from whitespace_api.agents.brief import prompts
from whitespace_api.agents.llm import CallSpec
from whitespace_api.core import tasks
from whitespace_api.core.config import Settings, get_settings
from whitespace_api.main import app
from whitespace_api.services import briefs as brief_service

URL = f"/api/v1/markets/THA/brief?exporter=PAK&hs6={TOWELS}"
DRAFT = prompts.Draft(
    headline="Thailand is growing fast.",
    why_now=[prompts.DraftPoint(text="Imports grew 19% a year.", refs=["F2"])],
    entry_checks=["Check labelling rules"],
    roadmap=[prompts.DraftStep(title="Find importers", detail="Start with distributors.")],
)


@pytest.fixture
def model_calls(
    monkeypatch: pytest.MonkeyPatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> Iterator[list[str]]:
    """Fake LLM, no web search, background jobs on the test database, limit of 2/day."""
    calls: list[str] = []

    def fake_get_chat_model(spec: CallSpec, settings: Any = None) -> Any:
        calls.append(spec.tier)
        raw = AIMessage(
            content="",
            usage_metadata={"input_tokens": 300, "output_tokens": 80, "total_tokens": 380},
            response_metadata={"model_name": "fake"},
        )
        return RunnableLambda(lambda _: {"raw": raw, "parsed": DRAFT})

    monkeypatch.setattr(brief_service.llm, "get_chat_model", fake_get_chat_model)
    monkeypatch.setattr(tasks, "session_factory", db_sessionmaker)
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,  # type: ignore[call-arg]
        brief_daily_limit=2,
    )
    yield calls
    app.dependency_overrides.pop(get_settings, None)


async def test_missing_until_requested(user: AsyncClient, model_calls: list[str]) -> None:
    assert (await user.get(URL)).json()["status"] == "missing"
    assert model_calls == []  # opening a market never spends tokens


async def test_request_generates_in_background_then_serves_cache(
    user: AsyncClient, model_calls: list[str]
) -> None:
    started = await user.post(URL)
    assert started.status_code == 202 and started.json()["status"] == "pending"
    await tasks.wait_for_jobs()

    ready = (await user.get(URL)).json()
    assert ready["status"] == "ready" and ready["generated_at"]
    assert ready["content"]["why_now"][0]["text"] == "Imports grew 19% a year."
    assert ready["content"]["research_available"] is False  # no search key in tests
    assert ready["usage"] == {
        "calls": 1,  # no sources, so no extraction call
        "input_tokens": 300,
        "output_tokens": 80,
        "models": ["fake"],
    }

    again = await user.post(URL)
    assert again.status_code == 200 and again.json()["status"] == "ready"
    assert model_calls == ["main"]  # the second request reused the brief


async def test_daily_limit(user: AsyncClient, model_calls: list[str]) -> None:
    for market, hs6 in (("THA", TOWELS), ("USA", TOWELS)):
        await user.post(f"/api/v1/markets/{market}/brief?exporter=PAK&hs6={hs6}")
        await tasks.wait_for_jobs()
    limited = await user.post(f"/api/v1/markets/USA/brief?exporter=PAK&hs6={BED_LINEN}")
    assert limited.status_code == 429 and "limit" in limited.json()["detail"]


async def test_unknown_market(user: AsyncClient, model_calls: list[str]) -> None:
    response = await user.post(f"/api/v1/markets/CHN/brief?exporter=PAK&hs6={TOWELS}")
    assert response.status_code == 404 and model_calls == []


async def test_failure_is_recorded_and_can_be_retried(
    user: AsyncClient, model_calls: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(spec: CallSpec, settings: Any = None) -> Any:
        def fail(_: Any) -> Any:
            raise RuntimeError("provider down")

        return RunnableLambda(fail)

    monkeypatch.setattr(brief_service.llm, "get_chat_model", broken)
    await user.post(URL)
    await tasks.wait_for_jobs()
    failed = (await user.get(URL)).json()
    assert failed["status"] == "failed" and "provider" not in failed["error"]  # no internals


async def test_requires_sign_in(client: AsyncClient) -> None:
    assert (await client.get(URL)).status_code == 401
    assert (await client.post(URL)).status_code == 401
