"""All runtime settings, read from environment variables (or a .env file).

Every deploy target (local Docker, Azure Container Apps, anything else) differs
only in these values, never in code.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from dotenv import dotenv_values
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    NoDecode,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

LLMProvider = Literal["gemini", "groq", "ollama"]

# Field -> variable prefix. GOOGLE_API_KEY, GOOGLE_API_KEY_1, GOOGLE_API_KEY_2, ... all count.
KEY_POOLS = {"google_api_keys": "GOOGLE_API_KEY", "groq_api_keys": "GROQ_API_KEY"}


def collect_numbered(values: Mapping[str, str | None], prefix: str) -> list[str]:
    """`PREFIX` then `PREFIX_1`, `PREFIX_2`, ... in numeric order; blanks and repeats dropped."""
    pattern = re.compile(rf"^{prefix}(?:_(\d+))?$")
    found = sorted(
        (int(m.group(1) or 0), value.strip())
        for name, value in values.items()
        if (m := pattern.match(name)) and value and value.strip()
    )
    return list(dict.fromkeys(value for _, value in found))


class NumberedKeysSource(PydanticBaseSettingsSource):
    """Collects numbered API keys (from .env files and the environment) into lists."""

    def __init__(self, settings_cls: type[BaseSettings], dotenv: DotEnvSettingsSource) -> None:
        super().__init__(settings_cls)
        files = dotenv.env_file
        self._files = [] if files is None else [files] if isinstance(files, str | Path) else files

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False  # values come from __call__

    def __call__(self) -> dict[str, Any]:
        values: dict[str, str | None] = {}
        for file in self._files:  # later files and the environment take precedence
            if Path(file).is_file():
                values.update(dotenv_values(file))
        values.update(os.environ)
        return {
            field: keys
            for field, prefix in KEY_POOLS.items()
            if (keys := collect_numbered(values, prefix))
        }


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- app ---
    app_env: Literal["local", "test", "staging", "production"] = "local"
    log_level: str = "INFO"
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # --- database ---
    database_url: str = "postgresql+asyncpg://whitespace:whitespace@localhost:5432/whitespace"

    # --- auth ---
    # Signs access tokens. Generate one with: openssl rand -hex 32
    jwt_secret: SecretStr = SecretStr("local-dev-secret-change-me-local-dev-secret")
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    # True whenever the site is served over HTTPS (always outside local).
    cookie_secure: bool = False
    # Public address of the web app. Google redirects back here, and the
    # web app forwards /api/* to this API, so cookies stay first-party.
    public_app_url: str = "http://localhost:3400"

    # --- Google sign-in (optional: the button hides itself when unset) ---
    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    # --- cache (optional until v1) ---
    redis_url: str | None = None

    # --- LLM ---
    llm_provider: LLMProvider = "gemini"
    llm_model: str = "gemini-flash-latest"
    llm_fallback_provider: LLMProvider | None = "groq"
    llm_fallback_model: str = "llama-3.3-70b-versatile"
    # One or many keys per provider (GOOGLE_API_KEY_1, _2, ...), used in rotation.
    google_api_keys: list[SecretStr] = Field(default_factory=list)
    groq_api_keys: list[SecretStr] = Field(default_factory=list)
    llm_keys_per_request: int = Field(
        default=2, ge=1, description="Keys of the main provider tried before falling back"
    )
    llm_key_rest_seconds: float = Field(
        default=60, gt=0, description="How long a rate-limited key sits out"
    )
    # Web research for briefs ("what's driving this").
    tavily_api_key: SecretStr | None = None
    # Monthly US imports (Census Bureau). EU monthly data (Eurostat) needs no key.
    census_api_key: SecretStr | None = None
    monthly_cache_days: int = Field(default=7, ge=1, description="Refresh monthly data after")
    # Ollama is for local development only, with a small model (see .env.example).
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        assert isinstance(dotenv_settings, DotEnvSettingsSource)
        numbered = NumberedKeysSource(settings_cls, dotenv_settings)
        return init_settings, env_settings, dotenv_settings, numbered, file_secret_settings

    @property
    def is_deployed(self) -> bool:
        return self.app_env in ("staging", "production")

    @model_validator(mode="after")
    def _deployed_needs_real_secrets(self) -> Settings:
        if self.is_deployed:
            secret = self.jwt_secret.get_secret_value()
            if len(secret) < 32 or secret.startswith("local-dev-secret"):
                raise ValueError("JWT_SECRET must be set to 32+ random characters")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true outside local development")
        return self

    @model_validator(mode="after")
    def _ollama_is_local_only(self) -> Settings:
        if self.is_deployed and "ollama" in (
            self.llm_provider,
            self.llm_fallback_provider,
        ):
            raise ValueError(
                "Ollama is for local development only; "
                "set LLM_PROVIDER/LLM_FALLBACK_PROVIDER to gemini or groq"
            )
        return self

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("jwt_secret", mode="before")
    @classmethod
    def _blank_secret_means_default(cls, value: object) -> object:
        # An empty JWT_SECRET= line in .env falls back to the local-only default.
        if value in ("", None):
            return "local-dev-secret-change-me-local-dev-secret"
        return value

    @field_validator("database_url")
    @classmethod
    def _force_async_driver(cls, value: str) -> str:
        # Hosted providers (Neon, Azure) hand out plain postgres:// URLs.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+asyncpg://" + value.removeprefix(prefix)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
