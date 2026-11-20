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
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import BaseModel

from whitespace_api.agents.keys import KeyPool, PooledKey
from whitespace_api.core.config import LLMProvider, Settings, get_settings

log = logging.getLogger(__name__)
TEMPERATURE = 0.2
# A key refused for auth/billing reasons won't recover by itself in seconds.
KEY_REFUSED_REST_SECONDS = 3600.0


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


def key_pool(provider: str) -> KeyPool:
    """The process-wide key pool of one provider (shared with non-chat calls)."""
    return _pools()[provider]


def is_key_refused(exc: BaseException) -> bool:
    """The key itself is unusable (invalid, no billing, no access): no point retrying soon."""
    if getattr(exc, "status_code", None) in (401, 403) or getattr(exc, "code", None) in (401, 403):
        return True
    # A quota message also says "check your plan and billing details": it's a rate
    # limit (the key recovers in a minute), not a refused key.
    if is_rate_limited(exc):
        return False
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    return (
        "permissiondenied" in name
        or "unauthenticated" in name
        or "api key not valid" in text
        or "billing" in text
    )


def is_rate_limited(exc: BaseException) -> bool:
    """Recognise a rate limit across provider SDKs (429 / quota exhausted)."""
    if getattr(exc, "status_code", None) == 429 or getattr(exc, "code", None) == 429:
        return True
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    return "ratelimit" in name or "resourceexhausted" in name or "429" in text or "quota" in text


Tier = Literal["main", "small"]


@dataclass(frozen=True)
class CallSpec:
    """What one LLM call needs: which tier, how much it may write, what shape to return."""

    tier: Tier = "main"
    max_output_tokens: int = 1024
    schema: type[BaseModel] | None = None  # structured output; returns {"raw", "parsed"}
    tools: Sequence[Any] = ()


def _model_name(provider: LLMProvider, tier: Tier, s: Settings) -> str:
    if provider == s.llm_provider:
        return s.llm_small_model if tier == "small" else s.llm_model
    return s.llm_fallback_small_model if tier == "small" else s.llm_fallback_model


def _model(
    provider: LLMProvider, key: PooledKey | None, s: Settings, spec: CallSpec
) -> BaseChatModel:
    model = _model_name(provider, spec.tier, s)
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        assert key is not None
        level = s.llm_thinking_level_small if spec.tier == "small" else s.llm_thinking_level_main
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=key.secret,
            temperature=TEMPERATURE,
            max_output_tokens=spec.max_output_tokens,
            thinking_config={"thinking_level": level},
            timeout=s.llm_timeout_seconds,
            max_retries=0,
        )
    if provider == "groq":
        from langchain_groq import ChatGroq

        assert key is not None
        return ChatGroq(
            model_name=model,
            api_key=key.secret,
            temperature=TEMPERATURE,
            max_tokens=spec.max_output_tokens,
            reasoning_effort="low",
            reasoning_format="hidden",
            timeout=s.llm_timeout_seconds,
            max_retries=0,
        )
    from langchain_ollama import ChatOllama

    # Always the small local model from OLLAMA_MODEL, whatever the tier says.
    return ChatOllama(
        model=s.ollama_model,
        base_url=s.ollama_base_url,
        temperature=TEMPERATURE,
        num_predict=spec.max_output_tokens,
    )


def _shape(chat: BaseChatModel, spec: CallSpec) -> Runnable[Any, Any]:
    if spec.schema is not None:
        return chat.with_structured_output(spec.schema, include_raw=True)
    if spec.tools:
        return chat.bind_tools(spec.tools)
    return chat


def _attempt(
    model: Runnable[Any, Any], key: PooledKey | None, pool: KeyPool | None
) -> Runnable[Any, Any]:
    """Wrap one attempt so a rate limit benches its key before the next attempt runs."""

    def on_error(exc: BaseException) -> None:
        if key is not None and pool is not None and is_key_refused(exc):
            pool.rest(key, seconds=KEY_REFUSED_REST_SECONDS)
            log.warning("%r refused (check its billing/validity); benched for 1 hour", key)
        elif key is not None and pool is not None and is_rate_limited(exc):
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
    keys_wanted: int,
    s: Settings,
    spec: CallSpec,
    pools: dict[str, KeyPool],
) -> list[Runnable[Any, Any]]:
    """The attempts for one provider: `keys_wanted` keys from its pool (Ollama needs none)."""
    if provider == "ollama":
        return [_attempt(_shape(_model(provider, None, s, spec), spec), None, None)]
    pool = pools[provider]
    return [
        _attempt(_shape(_model(provider, key, s, spec), spec), key, pool)
        for key in pool.take(keys_wanted)
    ]


def get_chat_model(
    spec: CallSpec | None = None,
    settings: Settings | None = None,
    pools: dict[str, KeyPool] | None = None,
) -> Runnable[Any, Any]:
    """A chat model for one request: rotated keys, then the fallback provider.

    `spec` picks the tier (main or small), the output cap, and structured output or
    tools. `settings` and `pools` default to the process-wide ones (tests pass their own).
    """
    s = settings or get_settings()
    spec = spec or CallSpec()
    p = pools if pools is not None else _pools()
    attempts = _plan(s.llm_provider, s.llm_keys_per_request, s, spec, p)
    if s.llm_fallback_provider is not None:
        attempts += _plan(s.llm_fallback_provider, 1, s, spec, p)
    if not attempts:
        raise LLMConfigError(
            f"No API key for {s.llm_provider}: set GOOGLE_API_KEY_1 / GROQ_API_KEY_1 in .env"
        )
    first, *rest = attempts
    return first.with_fallbacks(rest) if rest else first
