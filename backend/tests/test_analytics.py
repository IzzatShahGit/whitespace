"""First-party analytics: anonymous counts in, an admin-only summary out."""

from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient

from whitespace_api.core.config import Settings, get_settings
from whitespace_api.main import app
from whitespace_api.services import analytics

BROWSER = {"user-agent": "Mozilla/5.0 (X11; Linux x86_64) Firefox/140.0"}


def test_page_patterns_hide_ids_and_queries() -> None:
    assert analytics.page_pattern("/app/markets/630260/DEU?tab=prices") == (
        "/app/markets/[hs6]/[country]"
    )
    assert analytics.page_pattern("/app/markets/630260/DEU/deal") == (
        "/app/markets/[hs6]/[country]/deal"
    )
    assert (
        analytics.page_pattern("/app/ask/0b6f1a52-3c3e-4a7e-9a55-1f7d2c0f9e11") == "/app/ask/[id]"
    )
    assert analytics.page_pattern("/") == "/"
    assert analytics.page_pattern("https://evil.example/x") == ""


def test_visitor_ids_change_every_day() -> None:
    a = analytics.visitor_id("s", date(2026, 11, 18), "1.2.3.4", "ua")
    assert a == analytics.visitor_id("s", date(2026, 11, 18), "1.2.3.4", "ua") and len(a) == 16
    assert a != analytics.visitor_id("s", date(2026, 11, 19), "1.2.3.4", "ua")
    assert analytics.is_bot("Googlebot/2.1") and not analytics.is_bot(BROWSER["user-agent"])


@pytest.fixture
def admin() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(  # type: ignore[call-arg]
        _env_file=None, admin_emails=["ahmed@example.com"]
    )


async def test_events_are_counted_and_summarised(user: AsyncClient, admin: None) -> None:
    client = user  # the signed-in test client; events need no sign-in
    for path in ("/app/markets/630260/DEU", "/app/markets/630260/USA?tab=buyers", "/app"):
        r = await client.post(
            "/api/v1/events", json={"event": "page_view", "path": path}, headers=BROWSER
        )
        assert r.status_code == 204
    await client.post("/api/v1/events", json={"event": "deal_sheet_print"}, headers=BROWSER)
    await client.post(  # bots don't count
        "/api/v1/events", json={"event": "page_view", "path": "/"}, headers={"user-agent": "bot"}
    )
    bad = await client.post("/api/v1/events", json={"event": "anything"}, headers=BROWSER)
    assert bad.status_code == 422

    assert (await user.get("/api/v1/auth/me")).json()["is_admin"] is True
    stats = (await user.get("/api/v1/admin/stats")).json()
    assert stats["totals"]["page_views"] == 3 and stats["totals"]["visitors"] == 1
    assert stats["totals"]["users"] == 1 and stats["totals"]["sign_ups"] == 1
    assert stats["top_pages"][0] == {"name": "/app/markets/[hs6]/[country]", "count": 2}
    assert {"name": "Deal sheets printed", "count": 1} in stats["actions"]
    assert len(stats["days"]) == 30


async def test_stats_are_for_admins_only(client: AsyncClient, user: AsyncClient) -> None:
    assert (await user.get("/api/v1/auth/me")).json()["is_admin"] is False
    assert (await user.get("/api/v1/admin/stats")).status_code == 404  # not an admin


def test_admin_emails_match_case_insensitively() -> None:
    settings = Settings(_env_file=None, admin_emails=" Boss@Example.com ,")  # type: ignore[call-arg]
    assert settings.is_admin("boss@example.com") and not settings.is_admin("")
