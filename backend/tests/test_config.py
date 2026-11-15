import pytest
from pydantic import ValidationError

from whitespace_api.core.config import Settings


def test_plain_postgres_url_gets_async_driver() -> None:
    settings = Settings(database_url="postgres://u:p@host:5432/db")
    assert settings.database_url == "postgresql+asyncpg://u:p@host:5432/db"


DEPLOYED_OK = {"jwt_secret": "x" * 40, "cookie_secure": True}


@pytest.mark.parametrize("env", ["staging", "production"])
@pytest.mark.parametrize("field", ["llm_provider", "llm_fallback_provider"])
def test_ollama_refused_outside_local(env: str, field: str) -> None:
    with pytest.raises(ValidationError, match="local development only"):
        Settings(app_env=env, **DEPLOYED_OK, **{field: "ollama"})  # type: ignore[arg-type]


def test_deployed_requires_real_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(app_env="production", cookie_secure=True)


def test_deployed_requires_secure_cookies() -> None:
    with pytest.raises(ValidationError, match="COOKIE_SECURE"):
        Settings(app_env="production", jwt_secret="x" * 40)


def test_deployed_settings_accepted() -> None:
    assert Settings(app_env="production", **DEPLOYED_OK).is_deployed  # type: ignore[arg-type]


def test_ollama_allowed_locally() -> None:
    assert Settings(app_env="local", llm_provider="ollama").llm_provider == "ollama"


def test_cors_origins_accept_csv(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test")
    assert Settings().cors_origins == ["http://a.test", "http://b.test"]
