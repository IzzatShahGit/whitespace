"""API key pools: collection from .env, round robin, resting rate-limited keys."""

from __future__ import annotations

from pathlib import Path

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.runnables import RunnableLambda
from pydantic import SecretStr

from whitespace_api.agents import llm
from whitespace_api.agents.keys import KeyPool
from whitespace_api.core.config import Settings, collect_numbered


def test_collect_numbered_order_blanks_and_duplicates() -> None:
    values = {
        "GOOGLE_API_KEY_10": "k10",
        "GOOGLE_API_KEY_2": "k2",
        "GOOGLE_API_KEY": "plain",
        "GOOGLE_API_KEY_1": "k1",
        "GOOGLE_API_KEY_3": "  ",
        "GOOGLE_API_KEY_4": "k1",  # duplicate value
        "GOOGLE_API_KEYS": "not-matched",
        "GROQ_API_KEY_1": "other-provider",
    }
    assert collect_numbered(values, "GOOGLE_API_KEY") == ["plain", "k1", "k2", "k10"]


def test_settings_read_numbered_keys_from_env_file(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("GOOGLE_API_KEY_1=g1\nGOOGLE_API_KEY_2=g2\nGROQ_API_KEY_1=q1\n")
    s = Settings(_env_file=env)  # type: ignore[call-arg]
    assert [k.get_secret_value() for k in s.google_api_keys] == ["g1", "g2"]
    assert [k.get_secret_value() for k in s.groq_api_keys] == ["q1"]
    assert "g1" not in repr(s) and "g1" not in str(s.google_api_keys)  # stays secret


def test_environment_overrides_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / ".env"
    env.write_text("GOOGLE_API_KEY_1=from-file\n")
    monkeypatch.setenv("GOOGLE_API_KEY_1", "from-env")
    s = Settings(_env_file=env)  # type: ignore[call-arg]
    assert [k.get_secret_value() for k in s.google_api_keys] == ["from-env"]


def pool(n: int, now: list[float]) -> KeyPool:
    return KeyPool("gemini", [SecretStr(f"k{i}") for i in range(1, n + 1)], 60, lambda: now[0])


def test_round_robin() -> None:
    p = pool(3, [0.0])
    assert [p.take()[0].slot for _ in range(5)] == [1, 2, 3, 1, 2]


def test_take_several_distinct_keys() -> None:
    p = pool(3, [0.0])
    assert [k.slot for k in p.take(2)] == [1, 2]
    assert [k.slot for k in p.take(2)] == [2, 3]  # rotation advances by one request
    assert len(p.take(10)) == 3


def test_rate_limited_key_rests_then_returns() -> None:
    now = [0.0]
    p = pool(3, now)
    p.rest(p.take()[0])  # key 1 hit a limit
    assert [p.take()[0].slot for _ in range(4)] == [2, 3, 2, 3]
    now[0] = 61.0
    assert {p.take()[0].slot for _ in range(3)} == {1, 2, 3}


def test_all_resting_returns_soonest_to_recover() -> None:
    now = [0.0]
    p = pool(2, now)
    p.rest(p.take()[0])  # key 1 rests until 60
    now[0] = 10.0
    p.rest(p.take()[0])  # key 2 rests until 70
    assert p.take()[0].slot == 1


def test_empty_pool() -> None:
    assert KeyPool("groq", []).take() == []


def test_keys_never_in_repr() -> None:
    key = pool(1, [0.0]).take()[0]
    assert repr(key) == "<gemini key #1>" and "k1" not in repr(key)


class RateLimitedError(Exception):
    status_code = 429


def test_refused_key_rests_for_an_hour() -> None:
    now = [0.0]
    p = pool(2, now)
    p.rest(p.take()[0], seconds=llm.KEY_REFUSED_REST_SECONDS)
    now[0] = 120.0  # a rate-limited key would be back by now; a refused one isn't
    assert [p.take()[0].slot for _ in range(3)] == [2, 2, 2]


def test_refusal_detection() -> None:
    assert llm.is_key_refused(type("GooglePermissionDeniedError", (Exception,), {})())
    assert llm.is_key_refused(Exception("API key not valid. Please pass a valid API key."))
    assert not llm.is_key_refused(RateLimitedError("429"))


def test_rate_limit_detection() -> None:
    assert llm.is_rate_limited(RateLimitedError())
    assert llm.is_rate_limited(Exception("429 Too Many Requests"))
    assert llm.is_rate_limited(type("ResourceExhausted", (Exception,), {})())
    assert not llm.is_rate_limited(ValueError("bad input"))


async def test_failed_key_rests_and_next_attempt_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Key 1 is rate-limited: it gets benched and key 2 answers the same request."""
    pools = {"gemini": pool(2, [0.0]), "groq": KeyPool("groq", [])}

    def rate_limited(_: object) -> object:
        raise RateLimitedError("429 Too Many Requests")

    def fake_model(provider, key, settings, spec):  # type: ignore[no-untyped-def]
        if key.slot == 1:
            return RunnableLambda(rate_limited)
        return FakeListChatModel(responses=[f"answer from key {key.slot}"])

    monkeypatch.setattr(llm, "_model", fake_model)
    settings = Settings(_env_file=None, llm_fallback_provider=None)  # type: ignore[call-arg]
    chat = llm.get_chat_model(settings=settings, pools=pools)

    reply = await chat.ainvoke("hello")

    assert reply.content == "answer from key 2"
    assert [k.slot for k in pools["gemini"].take(2)] == [2, 1]  # key 1 resting: last resort


def test_no_keys_is_a_clear_error() -> None:
    settings = Settings(_env_file=None, llm_fallback_provider=None)  # type: ignore[call-arg]
    with pytest.raises(llm.LLMConfigError, match="GOOGLE_API_KEY_1"):
        llm.get_chat_model(settings=settings, pools={"gemini": KeyPool("gemini", [])})
