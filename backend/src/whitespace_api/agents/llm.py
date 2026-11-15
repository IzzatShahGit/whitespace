"""Chat-model factory. Switch providers with LLM_PROVIDER, never in code.

Every call builds one request plan:
  1. the main provider, with the next key(s) from its pool (round robin),
  2. then the fallback provider with its next key.
If an attempt fails it moves to the next; a rate-limited key is benched for a while.
Provider packages are imported lazily, so a missing key for one provider never
breaks the others.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from functools import lru_cache
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable, RunnableLambda

from whitespace_api.agents.keys import KeyPool, PooledKey
from whitespace_api.core.config import LLMProvider, Settings, get_settings

log = logging.getLogger(__name__)
TEMPERATURE = 0.2


class LLMConfigError(RuntimeError):
    """The selected provider has no usable key."""


@lru_cache
def _pools() -> dict[str, KeyPool]:
    """One pool per provider for this process, so rotation continues across requests."""
    settings = get_settings()
    return {
        "gemini": KeyPool("gemini", settings.google_api_keys, settings.llm_key_rest_seconds),
        "groq": KeyPool("groq", settings.groq_api_keys, settings.llm_key_rest_seconds),
    }


def is_rate_limited(exc: BaseException) -> bool:
    """Recognise a rate limit across provider SDKs (429 / quota exhausted)."""
    if getattr(exc, "status_code", None) == 429 or getattr(exc, "code", None) == 429:
        return True
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    return "ratelimit" in name or "resourceexhausted" in name or "429" in text or "quota" in text


def _model(provider: LLMProvider, model: str, key: PooledKey | None, s: Settings) -> BaseChatModel:
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        assert key is not None
        return ChatGoogleGenerativeAI(
            model=model, google_api_key=key.secret, temperature=TEMPERATURE, max_retries=0
        )
    if provider == "groq":
        from langchain_groq import ChatGroq

        assert key is not None
        return ChatGroq(
            model_name=model, api_key=key.secret, temperature=TEMPERATURE, max_retries=0
        )
    from langchain_ollama import ChatOllama

    # Always the small local model from OLLAMA_MODEL, whatever LLM_MODEL says.
    return ChatOllama(model=s.ollama_model, base_url=s.ollama_base_url, temperature=TEMPERATURE)


def _attempt(
    model: Runnable[Any, Any], key: PooledKey | None, pool: KeyPool | None
) -> Runnable[Any, Any]:
    """Wrap one attempt so a rate limit benches its key before the next attempt runs."""

    def on_error(exc: BaseException) -> None:
        if key is not None and pool is not None and is_rate_limited(exc):
            pool.rest(key)
            log.warning("%r rate-limited; resting it", key)
        else:
            log.warning("LLM attempt with %r failed: %s", key, type(exc).__name__)

    def run(value: Any, config: Any) -> Any:
        try:
            return model.invoke(value, config)
        except Exception as exc:
            on_error(exc)
            raise

    async def arun(value: Any, config: Any) -> Any:
        try:
            return await model.ainvoke(value, config)
        except Exception as exc:
            on_error(exc)
            raise

    return RunnableLambda(run, afunc=arun, name=f"llm:{key!r}")


def _plan(
    provider: LLMProvider,
    model: str,
    keys_wanted: int,
    s: Settings,
    tools: Sequence[Any],
    pools: dict[str, KeyPool],
) -> list[Runnable[Any, Any]]:
    """The attempts for one provider: `keys_wanted` keys from its pool (Ollama needs none)."""
    if provider == "ollama":
        built = _model(provider, model, None, s)
        return [_attempt(built.bind_tools(tools) if tools else built, None, None)]
    pool = pools[provider]
    attempts = []
    for key in pool.take(keys_wanted):
        chat = _model(provider, model, key, s)
        attempts.append(_attempt(chat.bind_tools(tools) if tools else chat, key, pool))
    return attempts


def get_chat_model(
    tools: Sequence[Any] = (),
    settings: Settings | None = None,
    pools: dict[str, KeyPool] | None = None,
) -> Runnable[Any, Any]:
    """A chat model for one request: rotated keys, then the fallback provider.

    Pass `tools` to get a tool-calling model (tools are bound on every attempt).
    `settings` and `pools` default to the process-wide ones (tests pass their own).
    """
    s = settings or get_settings()
    p = pools if pools is not None else _pools()
    attempts = _plan(s.llm_provider, s.llm_model, s.llm_keys_per_request, s, tools, p)
    if s.llm_fallback_provider is not None:
        attempts += _plan(s.llm_fallback_provider, s.llm_fallback_model, 1, s, tools, p)
    if not attempts:
        raise LLMConfigError(
            f"No API key for {s.llm_provider}: set GOOGLE_API_KEY_1 / GROQ_API_KEY_1 in .env"
        )
    first, *rest = attempts
    return first.with_fallbacks(rest) if rest else first
