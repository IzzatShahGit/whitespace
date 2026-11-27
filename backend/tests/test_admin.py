"""Admin side: accounts, visits, account actions, and the tracking that feeds them."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from whitespace_api.core.config import Settings, get_settings
from whitespace_api.main import app
from whitespace_api.models.analytics import Visit, VisitPage
from whitespace_api.models.user import User, UserActivityDay
from whitespace_api.services import geoip, visits

CHROME = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
}
IPHONE = {
    "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
}


# ---------- pure helpers ----------
def test_journey_paths_keep_codes_and_hide_record_ids() -> None:
    assert visits.journey_path("/app/markets/630260/DEU?tab=prices") == "/app/markets/630260/DEU"
    assert visits.journey_path("/app/ask/0b6f1a52-3c3e-4a7e-9a55-1f7d2c0f9e11") == "/app/ask/[id]"
    assert visits.journey_path("https://evil.example/x") == "/"


def test_sources_are_named_like_people_say_them() -> None:
    host = visits.referrer_host
    assert host("https://www.google.com.pk/", "whitespace.app") == "google.com.pk"
    assert host("https://whitespace.app/app", "whitespace.app") is None  # our own pages
    assert host("https://accounts.google.com/o/oauth2", "x") is None  # back from sign-in
    assert visits.source_of("google.com.pk", None) == "Google"
    assert visits.source_of("lnkd.in", None) == "LinkedIn"
    assert visits.source_of(None, None) == "Direct"
    assert visits.source_of("blog.example.org", None) == "blog.example.org"
    assert visits.source_of(None, "linkedin") == "LinkedIn"  # utm_source wins
    assert visits.source_of("google.com", "newsletter") == "newsletter"


def test_devices_browsers_and_systems() -> None:
    assert visits.device_of(IPHONE["user-agent"]) == "mobile"
    assert visits.browser_of(IPHONE["user-agent"]) == "Safari"
    assert visits.os_of(IPHONE["user-agent"]) == "iOS"
    assert visits.device_of(CHROME["user-agent"]) == "desktop"
    assert visits.browser_of(CHROME["user-agent"]) == "Chrome"
    assert visits.os_of(CHROME["user-agent"]) == "Windows"
    tablet = "Mozilla/5.0 (Linux; Android 14; SM-X710) Chrome/131.0 Safari/537.36"
    assert visits.device_of(tablet) == "tablet"


def test_country_lookup() -> None:
    assert geoip.country("127.0.0.1", "missing.mmdb") is None  # private: never looked up
    assert geoip.country("not an ip", "missing.mmdb") is None
    assert geoip.country("8.8.8.8", "/nowhere/missing.mmdb") is None  # no database: no country
    path = "data/geoip/country.mmdb"
    if not (Path(__file__).resolve().parents[2] / path).is_file():
        pytest.skip("run `make geoip` to test real lookups")
    assert geoip.country("8.8.8.8", path) == "US"


# ---------- fixtures ----------
@pytest.fixture
def admin() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(  # type: ignore[call-arg]
        _env_file=None, admin_emails=["ahmed@example.com"]
    )


@pytest.fixture
async def other(client: AsyncClient) -> AsyncIterator[AsyncClient]:
    """A second, ordinary account in its own browser."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/v1/auth/register",
            json={"email": "sara@example.com", "full_name": "Sara", "password": "linen-2026!"},
        )
        assert r.status_code == 201
        yield c


async def _id_of(db_sessionmaker: async_sessionmaker[AsyncSession], email: str) -> str:
    async with db_sessionmaker() as db:
        return str(await db.scalar(select(User.id).where(User.email == email)))


# ---------- tracking ----------
async def test_visits_follow_pages_time_and_sign_in(
    client: AsyncClient, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    first = {
        "event": "page_view",
        "path": "/",
        "referrer": "https://www.linkedin.com/feed/",
        "utm_campaign": "launch",
    }
    assert (await client.post("/api/v1/events", json=first, headers=CHROME)).status_code == 204
    await client.post(
        "/api/v1/events", json={"event": "engage", "path": "/", "seconds": 42}, headers=CHROME
    )
    await client.post(  # a runaway report is capped
        "/api/v1/events", json={"event": "engage", "path": "/", "seconds": 3000}, headers=CHROME
    )
    # They sign up in the same visit: the visit becomes theirs.
    await client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "full_name": "New", "password": "towels-2026!"},
    )
    await client.post(
        "/api/v1/events",
        json={"event": "page_view", "path": "/app/markets/630260/DEU"},
        headers=CHROME,
    )
    await client.post(  # bots are never visits
        "/api/v1/events", json={"event": "page_view", "path": "/"}, headers={"user-agent": "bot"}
    )

    async with db_sessionmaker() as db:
        rows = (await db.scalars(select(Visit))).all()
        assert len(rows) == 1
        visit = rows[0]
        assert (visit.source, visit.referrer, visit.utm_campaign) == (
            "LinkedIn",
            "linkedin.com",
            "launch",
        )
        assert (visit.device, visit.browser, visit.os) == ("desktop", "Chrome", "Windows")
        assert visit.pages == 2 and visit.landing == "/"
        assert visit.engaged_seconds == 42 + visits.MAX_ENGAGE
        assert visit.user_id is not None
        pages = (await db.scalars(select(VisitPage).order_by(VisitPage.at))).all()
        assert [(p.path, p.seconds) for p in pages] == [
            ("/", 42 + visits.MAX_ENGAGE),
            ("/app/markets/630260/DEU", 0),
        ]


async def test_sessions_record_last_seen_and_active_days(
    user: AsyncClient, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    async with db_sessionmaker() as db:
        u = await db.scalar(select(User).where(User.email == "ahmed@example.com"))
        assert u is not None and u.last_seen_at is not None
        first_seen = u.last_seen_at
        days = (await db.scalars(select(UserActivityDay.day))).all()
        assert len(days) == 1
    assert (await user.post("/api/v1/auth/refresh")).status_code == 200  # a quiet renewal
    async with db_sessionmaker() as db:
        u = await db.scalar(select(User).where(User.email == "ahmed@example.com"))
        assert u is not None and u.last_seen_at is not None and u.last_seen_at > first_seen
        assert len((await db.scalars(select(UserActivityDay.day))).all()) == 1  # same day


# ---------- admin pages ----------
async def test_admin_pages_are_hidden_from_everyone_else(
    user: AsyncClient, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    uid = await _id_of(db_sessionmaker, "ahmed@example.com")
    for method, url in [
        ("GET", "/api/v1/admin/stats"),
        ("GET", "/api/v1/admin/users"),
        ("GET", f"/api/v1/admin/users/{uid}"),
        ("GET", "/api/v1/admin/visits"),
        ("PATCH", f"/api/v1/admin/users/{uid}"),
        ("POST", f"/api/v1/admin/users/{uid}/sign-out"),
    ]:
        r = await user.request(method, url, json={} if method == "PATCH" else None)
        assert r.status_code == 404, url
    user.cookies.clear()
    assert (await user.get("/api/v1/admin/users")).status_code == 401


async def test_users_split_real_and_test_accounts(
    user: AsyncClient,
    other: AsyncClient,
    admin: None,
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    real = (await user.get("/api/v1/admin/users")).json()
    assert [u["email"] for u in real["users"]] == ["sara@example.com"]
    assert real["counts"] == {"real": 1, "test": 1, "disabled": 0}  # the admin is "test"
    row = real["users"][0]
    assert row["sign_in"] == "password" and row["active_days"] == 1 and not row["is_test"]
    assert "password_hash" not in row and "google_sub" not in row

    sara = row["id"]
    assert (
        await user.patch(f"/api/v1/admin/users/{sara}", json={"is_test": True})
    ).status_code == 204
    test = (await user.get("/api/v1/admin/users", params={"segment": "test"})).json()
    assert {u["email"] for u in test["users"]} == {"ahmed@example.com", "sara@example.com"}
    assert (await user.get("/api/v1/admin/users")).json()["total"] == 0
    found = (await user.get("/api/v1/admin/users", params={"segment": "all", "q": "SAR"})).json()
    assert [u["email"] for u in found["users"]] == ["sara@example.com"]

    stats = (await user.get("/api/v1/admin/stats")).json()
    assert stats["totals"]["users"] == 0 and stats["totals"]["test_users"] == 2


async def test_user_detail_shows_counts_not_content(
    user: AsyncClient,
    other: AsyncClient,
    admin: None,
) -> None:
    await other.put(
        "/api/v1/me/profile",
        json={"exporter": "PAK", "role": "manufacturer", "products": ["630260"]},
    )
    sara = (await user.get("/api/v1/admin/users")).json()["users"][0]["id"]
    detail = (await user.get(f"/api/v1/admin/users/{sara}")).json()
    assert detail["user"]["email"] == "sara@example.com"
    assert detail["open_sessions"] == 1 and len(detail["active_days"]) == 1
    if detail["profile"]:  # saved only if the seeded data accepts it
        assert detail["profile"]["exporter"]["code"] == "PAK"
    assert {m["name"] for m in detail["made"]} >= {"Questions asked", "Markets watched"}
    assert "password_hash" not in str(detail)
    missing = "00000000-0000-0000-0000-000000000000"
    assert (await user.get(f"/api/v1/admin/users/{missing}")).status_code == 404


async def test_disabling_signs_out_and_blocks_sign_in(
    user: AsyncClient,
    other: AsyncClient,
    admin: None,
) -> None:
    sara = (await user.get("/api/v1/admin/users")).json()["users"][0]["id"]
    r = await user.patch(f"/api/v1/admin/users/{sara}", json={"is_active": False})
    assert r.status_code == 204
    assert (await other.get("/api/v1/auth/me")).status_code == 401  # at once
    assert (await other.post("/api/v1/auth/refresh")).status_code == 401
    login = await other.post(
        "/api/v1/auth/login", json={"email": "sara@example.com", "password": "linen-2026!"}
    )
    assert login.status_code == 401 and "disabled" in login.text
    wrong = await other.post(
        "/api/v1/auth/login", json={"email": "sara@example.com", "password": "nope-nope-1"}
    )
    assert "disabled" not in wrong.text  # says nothing without the right password

    listed = (await user.get("/api/v1/admin/users", params={"status": "disabled"})).json()
    assert [u["email"] for u in listed["users"]] == ["sara@example.com"]
    detail = (await user.get(f"/api/v1/admin/users/{sara}")).json()
    assert [h["action"] for h in detail["history"]] == ["disable"]

    await user.patch(f"/api/v1/admin/users/{sara}", json={"is_active": True})
    again = await other.post(
        "/api/v1/auth/login", json={"email": "sara@example.com", "password": "linen-2026!"}
    )
    assert again.status_code == 200

    me = (await user.get("/api/v1/auth/me")).json()["id"]
    refused = await user.patch(f"/api/v1/admin/users/{me}", json={"is_active": False})
    assert refused.status_code == 409  # admins can't lock themselves (or each other) out


async def test_sign_out_everywhere(user: AsyncClient, other: AsyncClient, admin: None) -> None:
    sara = (await user.get("/api/v1/admin/users")).json()["users"][0]["id"]
    assert (await user.post(f"/api/v1/admin/users/{sara}/sign-out")).status_code == 204
    assert (await other.post("/api/v1/auth/refresh")).status_code == 401
    detail = (await user.get(f"/api/v1/admin/users/{sara}")).json()
    assert detail["open_sessions"] == 0 and detail["history"][0]["action"] == "sign_out"


async def test_visit_feed_and_summary_leave_out_test_accounts(
    user: AsyncClient, admin: None
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as stranger:
        await stranger.post(
            "/api/v1/events",
            json={"event": "page_view", "path": "/", "referrer": "https://www.google.com/"},
            headers=IPHONE,
        )
    await user.post(  # the admin browsing: a visit, but not a "real" one
        "/api/v1/events", json={"event": "page_view", "path": "/app"}, headers=CHROME
    )
    feed = (await user.get("/api/v1/admin/visits")).json()
    assert feed["total"] == 1 and feed["live_now"] == 1
    v = feed["visits"][0]
    assert (v["source"], v["device"], v["user"]) == ("Google", "mobile", None)
    assert [p["path"] for p in v["journey"]] == ["/"]
    everyone = (await user.get("/api/v1/admin/visits", params={"include_test": True})).json()
    assert everyone["total"] == 2

    summary = (await user.get("/api/v1/admin/stats")).json()["visits"]
    assert summary["visits"] == 1 and summary["sources"] == [{"name": "Google", "count": 1}]
    assert summary["devices"] == [{"name": "mobile", "count": 1}]
