"""Product ideas: Amazon best-seller captures (via Apify, mocked) and US import trends."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.seed import BED_LINEN, TOWELS
from tests.test_freight import route
from whitespace_api.core.config import Settings
from whitespace_api.integrations import apify
from whitespace_api.models import AmazonBestsellers, MarketSupplier
from whitespace_api.services import bestsellers, ideas
from whitespace_shared import us_imports
from whitespace_shared.amazon_categories import CATEGORIES, category_of, fee_category

NOW = datetime(2026, 11, 26, 12, tzinfo=UTC)
KITCHEN = "https://www.amazon.com/Best-Sellers-Kitchen-Dining/zgbs/kitchen/"


def item(rank: int, asin: str, *, url: str = KITCHEN, **extra: Any) -> dict[str, Any]:
    return {
        "position": rank,
        "category": "Amazon Best Sellers: Best Kitchen & Dining",
        "categoryUrl": url,
        "name": f"Towel set &amp; more {asin}",
        "price": 19.99,
        "currency": "$",
        "url": f"https://www.amazon.com/Towel-Set/dp/{asin}/ref=zg_bs_g_kitchen_{rank}?psc=1",
        **extra,
    }


# --- the category table --------------------------------------------------------------


def test_codes_map_to_amazon_categories_and_fees() -> None:
    assert category_of(TOWELS).key == "home"  # type: ignore[union-attr]
    assert category_of("611120").key == "baby"  # type: ignore[union-attr]  # before clothing
    assert category_of("640399").key == "fashion"  # type: ignore[union-attr]
    assert category_of("841810") is None  # fridges: not a small-seller product
    assert fee_category("640399") == "footwear"
    assert fee_category("611120") == "clothing"
    assert fee_category(TOWELS) == "home_kitchen"
    assert fee_category("841810") == "other"
    assert len({c.slug for c in CATEGORIES}) == len(CATEGORIES)


# --- parsing a run -------------------------------------------------------------------


def test_parse_keeps_top_ten_of_known_categories() -> None:
    raw = [
        item(1, "B000000001"),
        item(2, "B000000002", price=None),
        item(3, "B000000003", currency="€"),
        item(11, "B000000011"),  # beyond the top 10
        item(1, "B00000000S", url=f"{KITCHEN}289668"),  # a subcategory
        item(1, "B00000000U", url="https://www.amazon.com/zgbs/books/"),  # not listed
        {"error": "no_results_found", "url": KITCHEN},
        item(1, "B000000001"),  # repeated
        # What the actor really returns: the start URL in `input`, its own fields.
        {"position": 4, "name": "Owala bottle", "url": "https://www.amazon.com/dp/B085DV8T75",
         "asin": "B085DV8T75", "price": None, "stars": 4.6, "reviewsCount": 154219,
         "categoryUrl": "https://www.amazon.com/gp/bestsellers/kitchen?language=en",
         "input": "https://www.amazon.com/gp/bestsellers/kitchen"},
    ]  # fmt: skip
    out = bestsellers.parse_items(raw)
    assert [(i["category"], i["rank"]) for i in out] == [
        ("kitchen", 1),
        ("kitchen", 2),
        ("kitchen", 3),
        ("kitchen", 4),
    ]
    assert out[3] | {"name": ""} == {
        "category": "kitchen", "rank": 4, "name": "", "price": None, "list_price": None,
        "stars": 4.6, "reviews": 154219, "bought": None, "brand": None, "size": None,
        "asin": "B085DV8T75", "url": "https://www.amazon.com/dp/B085DV8T75",
    }  # fmt: skip
    first = out[0]
    assert first["name"] == "Towel set & more B000000001"
    assert first["url"] == "https://www.amazon.com/dp/B000000001"  # no tracking
    assert first["asin"] == "B000000001" and first["price"] == 19.99
    assert out[1]["price"] is None and out[2]["price"] is None  # missing; not dollars


def test_movement_against_last_week() -> None:
    before = [
        {"category": "kitchen", "rank": 1, "asin": "A"},
        {"category": "kitchen", "rank": 2, "asin": "B"},
    ]
    now = [
        {"category": "kitchen", "rank": 1, "asin": "B"},
        {"category": "kitchen", "rank": 2, "asin": "A"},
        {"category": "kitchen", "rank": 3, "asin": "C"},
        {"category": "kitchen", "rank": 4, "asin": None},
    ]
    moves = bestsellers.movement(now, before)
    assert moves == {("kitchen", 1): 1, ("kitchen", 2): -1, ("kitchen", 3): None}
    assert bestsellers.movement(now, None) == {}


def run(status: str, started: datetime, run_id: str = "r1") -> apify.Run:
    return apify.Run(run_id, status, started, None, "d1")


@pytest.mark.parametrize(
    ("last", "expected"),
    [
        (None, True),
        (run("RUNNING", NOW - timedelta(days=9)), False),
        (run("SUCCEEDED", NOW - timedelta(days=6)), False),
        (run("SUCCEEDED", NOW - timedelta(days=7)), True),
        (run("FAILED", NOW - timedelta(hours=3)), False),
        (run("ABORTED", NOW - timedelta(days=1)), True),
    ],
)
def test_runs_weekly_and_retries_failures_daily(last: apify.Run | None, expected: bool) -> None:
    assert bestsellers.due(last, NOW) is expected


async def test_codes_are_reused_by_asin_and_unsure_picks_dropped(
    monkeypatch: pytest.MonkeyPatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    async def options(db: AsyncSession, name: str, vector: Any) -> dict[str, str]:
        return {TOWELS: "Towels", BED_LINEN: "Bed linen"}

    async def choose(settings: Settings, name: str, found: dict[str, str]) -> Any:
        sure = "high" if name == "cotton towel (sold on Amazon as: Sure towel)" else "low"
        return [(TOWELS, sure, "why")], []

    async def no_vectors(texts: list[str], **_: Any) -> list[list[float]]:
        raise bestsellers.embeddings.EmbeddingError("down")

    async def names(settings: Settings, titles: list[str]) -> dict[str, str]:
        return {"Sure towel": "cotton towel"}

    monkeypatch.setattr(bestsellers, "plain_names", names)
    monkeypatch.setattr(bestsellers, "_options", options)
    monkeypatch.setattr(bestsellers.hs_finder, "choose", choose)
    monkeypatch.setattr(bestsellers.embeddings, "embed", no_vectors)
    items = [
        {"name": "Sure towel", "asin": "A"},
        {"name": "Vague thing", "asin": "B"},
        {"name": "Old friend", "asin": "C"},
    ]
    async with db_sessionmaker() as db:
        await bestsellers.guess_codes(
            db, Settings(_env_file=None), items, known={"C": {"hs6": BED_LINEN, "plain": "linen"}}
        )  # type: ignore[call-arg]
    assert [i["hs6"] for i in items] == [TOWELS, None, BED_LINEN]
    assert [i["plain"] for i in items] == ["cotton towel", None, "linen"]


def test_detailed_pages_give_price_size_and_volume() -> None:
    detailed = {
        "title": "Apple AirPods Pro 3",
        "asin": "B0FQFB8FMG",
        "url": "https://www.amazon.com/dp/B0FQFB8FMG?language=en",
        "input": "https://www.amazon.com/gp/bestsellers/electronics",
        "bestsellerPageData": {"categoryUrl": "https://www.amazon.com/gp/bestsellers/electronics",
                               "position": 2},
        "price": {"value": 149, "currency": "$"},
        "listPrice": {"value": 249, "currency": "$"},
        "stars": 4.4, "reviewsCount": 18368, "brand": "Apple",
        "monthlyPurchaseVolume": "10K+ bought in past month",
        "attributes": [
            {"key": "Product Dimensions", "value": "1.1 x 0.8 x 1.2 inches"},
            {"key": "Item Weight", "value": "0.32 ounces"},
        ],
    }  # fmt: skip
    [out] = bestsellers.parse_items([detailed])
    assert (out["category"], out["rank"], out["name"]) == ("electronics", 2, "Apple AirPods Pro 3")
    assert (out["price"], out["list_price"]) == (149, 249)
    assert out["bought"] == "10K+ bought in past month" and out["brand"] == "Apple"
    assert out["size"] == {"in": [1.2, 1.1, 0.8], "lb": 0.02, "packed": False}


@pytest.mark.parametrize(
    ("text", "sides"),
    [
        ("10 x 5 x 3 inches; 1.2 Pounds", [10.0, 5.0, 3.0]),
        ('3.5"L x 3.5"W x 10"H', [10.0, 3.5, 3.5]),
        ("25 x 10 x 5 cm", [9.84, 3.94, 1.97]),
        ("one size", None),
        ("200 x 10 x 5 inches", None),  # beyond any parcel: not trusted
    ],
)
def test_dimensions(text: str, sides: list[float] | None) -> None:
    assert bestsellers.parse_dimensions(text) == sides


def test_packed_size_wins_over_the_item() -> None:
    size = bestsellers.parse_size(
        [
            {"key": "Product Dimensions", "value": "8 x 3 x 3 inches"},
            {"key": "Item Weight", "value": "450 Grams"},
            {"key": "Package Dimensions", "value": "10 x 4 x 4 inches; 1.5 Pounds"},
        ]
    )
    assert size == {"in": [10.0, 4.0, 4.0], "lb": 1.5, "packed": True}
    assert bestsellers.parse_weight("450 Grams") == 0.992


# --- the job, against a fake Apify ---------------------------------------------------


class FakeApify:
    def __init__(self, items: list[dict[str, Any]], *, last_started: datetime) -> None:
        self.items = items
        self.last_started = last_started
        self.started: list[dict[str, Any]] = []
        self.charge: list[str] = []

    def _run(self, run_id: str, status: str = "SUCCEEDED") -> dict[str, Any]:
        return {
            "data": {
                "id": run_id,
                "status": status,
                "startedAt": self.last_started.isoformat(),
                "finishedAt": (self.last_started + timedelta(minutes=4)).isoformat(),
                "defaultDatasetId": f"ds-{run_id}",
            }
        }

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer secret"
        path = request.url.path
        if path.endswith("/runs/last"):
            return httpx.Response(200, json=self._run("r1"))
        if path.endswith("/runs") and request.method == "POST":
            self.started.append(json.loads(request.content))
            self.charge.append(request.url.params["maxTotalChargeUsd"])
            return httpx.Response(201, json=self._run("r2", "READY"))
        if path == "/v2/datasets/ds-r1/items":
            return httpx.Response(200, json=self.items)
        return httpx.Response(404)


def full_run() -> list[dict[str, Any]]:
    """Ten items in every category, all called towels."""
    out = []
    for c in CATEGORIES:
        for rank in range(1, 11):
            url = f"https://www.amazon.com/gp/bestsellers/{c.slug}"
            out.append(item(rank, f"B{c.key[:4].upper():0<4}{rank:05d}X", url=url))
    return out


@pytest.fixture
def no_guessing(monkeypatch: pytest.MonkeyPatch) -> None:
    async def guess(
        db: AsyncSession, settings: Settings, items: list[dict[str, Any]], **_: Any
    ) -> None:
        for i in items:
            i["hs6"] = TOWELS

    monkeypatch.setattr(bestsellers, "guess_codes", guess)


async def test_job_does_nothing_without_a_token(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    async with db_sessionmaker() as db, httpx.AsyncClient() as client:
        out = await bestsellers.refresh(db, client, Settings(_env_file=None))  # type: ignore[call-arg]
    assert out.startswith("skipped")


async def test_job_saves_new_runs_and_starts_weekly(
    db_sessionmaker: async_sessionmaker[AsyncSession], no_guessing: None
) -> None:
    fake = FakeApify(full_run(), last_started=NOW - timedelta(days=8))
    settings = Settings(_env_file=None, apify_token="secret")  # type: ignore[call-arg]
    async with (
        db_sessionmaker() as db,
        httpx.AsyncClient(transport=httpx.MockTransport(fake.handler)) as client,
    ):
        out = await bestsellers.refresh(db, client, settings, now=NOW)
        assert "saved 150 items from run r1" in out and "started run r2" in out
        assert fake.charge == ["0.90"]  # every run carries the cost cap
        assert fake.started[0]["maxItemsPerStartUrl"] == 10
        assert len(fake.started[0]["categoryUrls"]) == len(CATEGORIES)
        again = await bestsellers.refresh(db, client, settings, now=NOW)
        assert again.startswith("nothing new")

        fake.last_started = NOW - timedelta(days=1)  # a fresh run: nothing to start
        assert "started" not in await bestsellers.refresh(db, client, settings, now=NOW)
        rows = list(await db.scalars(select(AmazonBestsellers)))
    assert len(rows) == 1 and rows[0].items[0]["hs6"] == TOWELS


async def test_a_mostly_empty_run_keeps_last_weeks_lists(
    db_sessionmaker: async_sessionmaker[AsyncSession], no_guessing: None
) -> None:
    fake = FakeApify(full_run()[:20], last_started=NOW - timedelta(days=1))
    settings = Settings(_env_file=None, apify_token="secret")  # type: ignore[call-arg]
    async with (
        db_sessionmaker() as db,
        httpx.AsyncClient(transport=httpx.MockTransport(fake.handler)) as client,
    ):
        assert (await bestsellers.refresh(db, client, settings, now=NOW)) == "nothing new"
        assert list(await db.scalars(select(AmazonBestsellers))) == []


# --- US import trends ----------------------------------------------------------------


def imports(rows: dict[str, list[int]]) -> us_imports.Imports:
    return us_imports.Imports(
        source="Census",
        source_url="https://api.census.gov/",
        first_month="2024-10",
        last_month="2026-09",
        built="2026-11-25",
        series={h: us_imports.Series(h, "DESC", tuple(m)) for h, m in rows.items()},
    )


def flat(before: int, after: int, *, last_quarter: int | None = None) -> list[int]:
    months = [before] * 12 + [after] * 12
    if last_quarter is not None:
        months[-3:] = [last_quarter] * 3
    return months


def test_rising_needs_size_growth_and_a_rising_last_quarter() -> None:
    data = imports(
        {
            TOWELS: flat(2_000, 3_000),  # +50%, $36M: rising
            BED_LINEN: flat(2_000, 2_050),  # +2.5%: too little
            "630710": flat(100, 300),  # $3.6M: too small
            "950300": flat(2_000, 3_000, last_quarter=1_500),  # fading: last quarter down
            "841810": flat(2_000, 4_000),  # not an Amazon category we map
        }
    )
    assert [s.hs6 for s in ideas.rising_series(data)] == [TOWELS]
    trends = {t.category.key: t for t in ideas.category_trends(data)}
    assert trends["home"].growth == pytest.approx(
        (3_000 + 2_050 + 300) / (2_000 + 2_000 + 100) - 1, abs=1e-4
    )
    assert trends["home"].codes == 3 and trends["toys"].recent_growth == pytest.approx(-0.25)


def test_the_shipped_import_file_is_usable() -> None:
    data = us_imports.load()
    assert data is not None and len(data.series) >= 200
    assert all(category_of(h) for h in data.series)
    assert ideas.rising_series(data)


async def test_starting_point_is_the_biggest_supplier_we_can_ship_from(
    seeded: None, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    def supplier(code: str, share: float, per_kg: float) -> MarketSupplier:
        return MarketSupplier(
            market="USA", hs6=TOWELS, supplier=code, value_usd=1e6, share_start=share,
            share_end=share, unit_price_usd_kg=per_kg,
        )  # fmt: skip

    async with db_sessionmaker() as db:
        # China supplies more, but there's no priced route from it here; Pakistan has one.
        db.add_all([supplier("CHN", 0.6, 5.0), supplier("PAK", 0.3, 7.3)])
        db.add(route(dest="USA", sea_nm=11_600.0, dest_port="New York", dest_port_code="USNYC"))
        await db.commit()
        points = await ideas.starting_points(db, {TOWELS: 2.0})
    start = points[TOWELS]
    assert start.origin.code == "PAK" and start.share == 0.3 and start.price_per_kg_usd == 7.3
    assert start.unit_cost_usd == pytest.approx(7.3 * 2.0 * 0.453592, abs=0.01)


# --- the endpoint --------------------------------------------------------------------


async def test_ideas_page_shows_lists_movement_and_sources(
    client: AsyncClient, seeded: None, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    empty = (await client.get("/api/v1/public/ideas")).json()
    assert empty["amazon"] is None and len(empty["categories"]) == len(CATEGORIES)
    assert empty["imports"]["source"].startswith("US Census Bureau")

    def kitchen(*asins: str, hs6: str | None = TOWELS) -> list[dict[str, Any]]:
        return [
            {"category": "kitchen", "rank": r, "name": a, "price": 9.5, "asin": a,
             "url": f"https://www.amazon.com/dp/{a}", "hs6": hs6}
            for r, a in enumerate(asins, start=1)
        ]  # fmt: skip

    async with db_sessionmaker() as db:
        db.add(
            AmazonBestsellers(
                run_id="old", captured_at=NOW - timedelta(days=7), items=kitchen("A", "B")
            )
        )
        db.add(
            AmazonBestsellers(run_id="new", captured_at=NOW, items=kitchen("B", "C", hs6="999999"))
        )
        await db.commit()

    out = await client.get("/api/v1/public/ideas")
    assert out.status_code == 200 and "max-age" in out.headers["Cache-Control"]
    assert out.json()["amazon"]["lists"][0]["items"][0]["start"] is None  # no US suppliers seeded
    amazon = out.json()["amazon"]
    assert amazon["previous_at"] is not None
    [lst] = amazon["lists"]
    assert lst["category"]["key"] == "kitchen"
    assert lst["category"]["bestsellers_url"] == "https://www.amazon.com/gp/bestsellers/kitchen"
    b, c = lst["items"]
    assert (b["moved"], b["is_new"]) == (1, False) and (c["moved"], c["is_new"]) == (None, True)
    assert b["hs6"] is None and b["product_name"] is None  # a code we don't have isn't offered
    assert b["fee_category"] == "home_kitchen"
