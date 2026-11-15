"""Recent movement: source parsing, the 12-month windows, and on-demand caching."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.seed import TOWELS
from whitespace_api.integrations import monthly_trade as source
from whitespace_api.models import MonthlyTradeCache
from whitespace_api.services import recent

NOW = datetime(2026, 11, 16, tzinfo=UTC)


def months(n: int, end: tuple[int, int] = (2026, 9)) -> list[str]:
    year, month = end
    out = []
    for _ in range(n):
        out.append(f"{year}-{month:02d}")
        year, month = (year, month - 1) if month > 1 else (year - 1, 12)
    return out[::-1]


def payload(n: int = 30) -> dict[str, Any]:
    """Total 100/month for the older half, 120/month recently. Pakistan 5 -> 12; China 60 -> 50."""
    ms = months(n)
    recent_ms = set(ms[-12:])
    return {
        "source": "eurostat",
        "currency": "EUR",
        "total": {m: 120.0 if m in recent_ms else 100.0 for m in ms},
        "partners": {
            "CN": {"name": "China", "values": {m: 50.0 if m in recent_ms else 60.0 for m in ms}},
            "PK": {"name": "Pakistan", "values": {m: 12.0 if m in recent_ms else 5.0 for m in ms}},
            "TR": {"name": "Türkiye", "values": dict.fromkeys(ms, 0.0)},
        },
    }


def test_summary_windows_and_shares() -> None:
    result = recent.summarise(payload(), exporter_code="PK", fetched_at=NOW, stale=False)
    assert result.latest_month == "2026-09"
    assert len(result.months) == 24 and result.months[-1].month == "2026-09"
    assert result.change_12m == pytest.approx(0.20)
    assert result.exporter_share_recent == pytest.approx(0.10)
    assert result.exporter_share_before == pytest.approx(0.05)
    assert [s.name for s in result.suppliers] == ["China", "Pakistan"]  # Türkiye sold nothing
    assert result.suppliers[0].share_before == pytest.approx(0.60)
    assert result.months[-1].exporter == 12.0
    assert result.note and "Netherlands" in result.note  # EU source explains share differences


def test_summary_with_less_than_two_years() -> None:
    result = recent.summarise(payload(15), exporter_code="PK", fetched_at=NOW, stale=False)
    assert result.change_12m is None and result.exporter_share_before is None
    assert result.suppliers[0].share_before is None


def test_summary_for_exporter_not_in_source() -> None:
    result = recent.summarise(payload(), exporter_code=None, fetched_at=NOW, stale=False)
    assert result.exporter_share_recent == 0 and result.months[0].exporter == 0


def test_summary_with_no_data() -> None:
    with pytest.raises(recent.UnavailableError):
        recent.summarise(
            {"source": "census", "currency": "USD", "total": {}, "partners": {}},
            exporter_code=None,
            fetched_at=NOW,
            stale=False,
        )


def test_history_starts_far_enough_back() -> None:
    assert recent._since(date(2026, 11, 16)) == date(2023, 12, 1)


async def test_eurostat_parsing() -> None:
    body = {
        "id": ["freq", "reporter", "partner", "product", "flow", "indicators", "time"],
        "size": [1, 1, 3, 1, 1, 1, 2],
        "dimension": {
            "freq": {"category": {"index": {"M": 0}}},
            "reporter": {"category": {"index": {"DE": 0}}},
            "partner": {
                "category": {
                    "index": {"PK": 0, "WORLD": 1, "EXT_EU27_2020": 2},
                    "label": {"PK": "Pakistan", "WORLD": "World", "EXT_EU27_2020": "Extra-EU"},
                }
            },
            "product": {"category": {"index": {"630260": 0}}},
            "flow": {"category": {"index": {"1": 0}}},
            "indicators": {"category": {"index": {"VALUE_IN_EUROS": 0}}},
            "time": {"category": {"index": {"2026-08": 0, "2026-09": 1}}},
        },
        # flat index = partner * 2 + time
        "value": {"0": 5.0, "1": 6.0, "2": 100.0, "3": 110.0, "4": 90.0},
    }
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=body))
    async with httpx.AsyncClient(transport=transport) as client:
        result = await source.fetch_eurostat(client, "DEU", TOWELS, date(2026, 8, 1))
    assert result["total"] == {"2026-08": 100.0, "2026-09": 110.0}
    assert list(result["partners"]) == ["PK"]  # aggregates skipped
    assert result["partners"]["PK"] == {
        "name": "Pakistan",
        "values": {"2026-08": 5.0, "2026-09": 6.0},
    }


async def test_census_parsing_and_key_not_leaked() -> None:
    rows = [
        ["CTY_CODE", "CTY_NAME", "GEN_VAL_MO", "I_COMMODITY", "COMM_LVL", "time"],
        ["-", "TOTAL FOR ALL COUNTRIES", "1000", TOWELS, "HS6", "2026-09"],
        ["0003", "EUROPEAN UNION", "200", TOWELS, "HS6", "2026-09"],
        ["5350", "PAKISTAN", "150", TOWELS, "HS6", "2026-09"],
    ]
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=rows))
    async with httpx.AsyncClient(transport=transport) as client:
        result = await source.fetch_census(client, TOWELS, date(2026, 9, 1), "secret-key")
    assert result["total"] == {"2026-09": 1000.0}
    assert result["partners"] == {"5350": {"name": "Pakistan", "values": {"2026-09": 150.0}}}

    failing = httpx.MockTransport(lambda r: httpx.Response(500))
    async with httpx.AsyncClient(transport=failing) as client:
        with pytest.raises(source.SourceError) as caught:
            await source.fetch_census(client, TOWELS, date(2026, 9, 1), "secret-key")
    assert "secret-key" not in str(caught.value)


@pytest.fixture
def fetches(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    async def fake_fetch(source_name: str, market: str, hs6: str, settings: Any) -> dict[str, Any]:
        calls.append(market)
        return payload()

    monkeypatch.setattr(recent, "_fetch", fake_fetch)
    return calls


URL = f"/api/v1/markets/DEU/recent?exporter=PAK&hs6={TOWELS}"


async def test_fetches_once_then_serves_from_cache(user: AsyncClient, fetches: list[str]) -> None:
    first = await user.get(URL)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["source"] == "Eurostat (EU customs)" and body["currency"] == "EUR"
    assert body["exporter_share_recent"] == pytest.approx(0.10) and body["stale"] is False
    assert (await user.get(URL)).status_code == 200
    assert fetches == ["DEU"]  # second request came from the cache


async def test_old_copy_served_when_source_is_down(
    user: AsyncClient,
    fetches: list[str],
    db_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await user.get(URL)
    async with db_sessionmaker() as s:  # age the cached copy past its refresh time
        await s.execute(
            update(MonthlyTradeCache).values(fetched_at=datetime.now(UTC) - timedelta(days=30))
        )
        await s.commit()

    async def down(*_: Any) -> None:
        raise source.SourceError("timeout")

    monkeypatch.setattr(recent, "_fetch", down)
    response = await user.get(URL)
    assert response.status_code == 200 and response.json()["stale"] is True


async def test_unavailable_without_cache(
    user: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def down(*_: Any) -> None:
        raise source.SourceError("timeout")

    monkeypatch.setattr(recent, "_fetch", down)
    response = await user.get(URL)
    assert response.status_code == 503 and "isn't responding" in response.json()["detail"]


async def test_markets_outside_eu_and_us(user: AsyncClient, fetches: list[str]) -> None:
    response = await user.get(f"/api/v1/markets/THA/recent?exporter=PAK&hs6={TOWELS}")
    assert response.status_code == 404 and fetches == []
