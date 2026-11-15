"""Chat-model factory. Switch providers with LLM_PROVIDER, never in code.

Provider packages are imported lazily, so a missing key for one provider
never breaks the others.
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable

from whitespace_api.core.config import LLMProvider, Settings, get_settings


class LLMConfigError(RuntimeError):
    """Raised when the selected provider is missing its key."""


def _build(provider: LLMProvider, model: str, settings: Settings) -> BaseChatModel:
    if provider == "gemini":
        if settings.google_api_key is None:
            raise LLMConfigError("GOOGLE_API_KEY is not set")
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model, google_api_key=settings.google_api_key, temperature=0.2
        )
    if provider == "groq":
        if settings.groq_api_key is None:
            raise LLMConfigError("GROQ_API_KEY is not set")
        from langchain_groq import ChatGroq

        return ChatGroq(model_name=model, api_key=settings.groq_api_key, temperature=0.2)
    from langchain_ollama import ChatOllama

    # Always the small local model from OLLAMA_MODEL, whatever LLM_MODEL says.
    return ChatOllama(
        model=settings.ollama_model, base_url=settings.ollama_base_url, temperature=0.2
    )


def get_chat_model(settings: Settings | None = None) -> Runnable:  # type: ignore[type-arg]
    """Primary model, with automatic fallback when one is configured."""
    settings = settings or get_settings()
    primary = _build(settings.llm_provider, settings.llm_model, settings)
    if settings.llm_fallback_provider is None:
        return primary
    try:
        fallback = _build(settings.llm_fallback_provider, settings.llm_fallback_model, settings)
    except LLMConfigError:
        return primary  # fallback not configured: run on the primary alone
    return primary.with_fallbacks([fallback])
