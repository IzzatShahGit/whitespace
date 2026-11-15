"""Check every configured API key with a minimal, free call. Prints slot numbers and
pass/fail only, never key values.

    make check-keys
"""

from __future__ import annotations

import httpx

from whitespace_api.core.config import get_settings

TIMEOUT = 20


def _gemini(key: str) -> str:
    # Listing models costs nothing and proves the key is accepted.
    r = httpx.get(
        "https://generativelanguage.googleapis.com/v1beta/models",
        params={"key": key, "pageSize": 1},
        timeout=TIMEOUT,
    )
    return "ok" if r.status_code == 200 else f"failed (HTTP {r.status_code})"


def _groq(key: str) -> str:
    r = httpx.get(
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {key}"},
        timeout=TIMEOUT,
    )
    return "ok" if r.status_code == 200 else f"failed (HTTP {r.status_code})"


def _census(key: str) -> str:
    r = httpx.get(
        "https://api.census.gov/data/timeseries/intltrade/imports/hs",
        params={
            "get": "GEN_VAL_MO",
            "I_COMMODITY": "630260",
            "COMM_LVL": "HS6",
            "CTY_CODE": "5350",
            "time": "2025-01",
            "key": key,
        },
        timeout=TIMEOUT,
    )
    return "ok" if r.status_code == 200 else f"failed (HTTP {r.status_code})"


def _tavily(key: str) -> str:
    r = httpx.get(
        "https://api.tavily.com/usage", headers={"Authorization": f"Bearer {key}"}, timeout=TIMEOUT
    )
    return "ok" if r.status_code == 200 else f"failed (HTTP {r.status_code})"


def _report(label: str, result: str) -> bool:
    print(f"  {label:<22} {result}")
    return result == "ok"


def main() -> int:
    settings = get_settings()
    checks: list[bool] = []
    print("LLM keys (rotated round robin):")
    for provider, keys, check in (
        ("gemini", settings.google_api_keys, _gemini),
        ("groq", settings.groq_api_keys, _groq),
    ):
        if not keys:
            print(f"  {provider:<22} none configured")
        for slot, key in enumerate(keys, start=1):
            checks.append(_report(f"{provider} key #{slot}", check(key.get_secret_value())))
    print("Data and research keys:")
    tavily = settings.tavily_api_key.get_secret_value() if settings.tavily_api_key else None
    census = settings.census_api_key.get_secret_value() if settings.census_api_key else None
    for name, value, check in (
        ("CENSUS_API_KEY", census, _census),
        ("TAVILY_API_KEY", tavily, _tavily),
    ):
        if not value:
            print(f"  {name:<22} not set")
            continue
        checks.append(_report(name, check(value)))
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
