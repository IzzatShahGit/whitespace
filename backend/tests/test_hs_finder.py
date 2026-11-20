"""Finding an HS code: candidate fusion, embeddings refresh, model picks kept to the
candidates, fallbacks, photos and limits. Embeddings are faked (hashed words) so the
real pgvector query runs without a network."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from typing import Any

import pytest
from httpx import AsyncClient
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from whitespace_api.agents.llm import CallSpec
from whitespace_api.core.config import Settings, get_settings
from whitespace_api.integrations import embeddings
from whitespace_api.jobs import embed_products
from whitespace_api.main import app
from whitespace_api.models.trade import Product, ProductEmbedding
from whitespace_api.services import hs_finder

RAW = AIMessage(content="", response_metadata={"model_name": "fake"})
MORE = {
    "611020": "Jerseys, pullovers, cardigans, waistcoats and similar articles: of cotton, "
    "knitted or crocheted",
    "620520": "Shirts: men's or boys', of cotton (not knitted or crocheted)",
    "640411": "Sports footwear: tennis shoes, basketball shoes, gym shoes, training shoes "
    "and the like, with outer soles of rubber or plastics and uppers of textile materials",
}
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def fake_vector(text: str) -> list[float]:
    vector = [0.0] * embeddings.DIMENSIONS
    for word in text.lower().replace(",", " ").replace(":", " ").split():
        vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % embeddings.DIMENSIONS] += 1
    return embeddings.unit(vector)


@pytest.fixture
async def catalogue(
    seeded: None,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[list[int]]:
    calls: list[int] = []

    async def fake_embed(texts: list[str], *, task: str, attempts: int = 3) -> list[list[float]]:
        calls.append(len(texts))
        return [fake_vector(t) for t in texts]

    monkeypatch.setattr(embeddings, "embed", fake_embed)
    async with db_sessionmaker() as db:
        db.add_all(Product(hs6=h, description=d, hs_revision="HS17") for h, d in MORE.items())
        await db.commit()
        await embed_products.run(db)
    yield calls


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Picks one real candidate, one invented code and a duplicate; describes photos."""
    prompts: list[str] = []

    def fake(spec: CallSpec, settings: Any = None) -> Any:
        def run(messages: Any) -> Any:
            prompts.append(str(messages[-1][1]))
            if spec.schema is None:  # the photo
                return AIMessage(content="A grey hooded sweatshirt of knitted cotton fleece.")
            choice = hs_finder._Choice(
                picks=[
                    hs_finder._Pick(hs6="611020", confidence="high", why="Knitted cotton top."),
                    hs_finder._Pick(hs6="999999", confidence="high", why="Invented."),
                    hs_finder._Pick(hs6="6110.20", confidence="low", why="Same again."),
                ],
                questions=["Is it knitted or woven?"],
            )
            return {"raw": RAW, "parsed": choice}

        return RunnableLambda(run)

    monkeypatch.setattr(hs_finder.llm, "get_chat_model", fake)
    yield prompts


def test_rank_fusion_rewards_agreement() -> None:
    assert hs_finder.fuse(["a", "b", "c"], ["b", "c", "a"], ["b"]) == ["b", "a", "c"]
    assert hs_finder.fuse([], ["x"]) == ["x"]


async def test_refresh_embeds_only_what_changed(
    catalogue: list[int], db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    async with db_sessionmaker() as db:
        total = await db.scalar(select(func.count()).select_from(ProductEmbedding))
        products = await db.scalar(select(func.count()).select_from(Product))
        assert total == products and catalogue == [products]
        assert await embed_products.run(db) == f"0 embedded, {products} unchanged, 0 removed"
        (await db.get(Product, "620520")).description = "Shirts: men's, of cotton, woven"  # type: ignore[union-attr]
        await db.commit()
        assert (await embed_products.run(db)).startswith("1 embedded")
    assert "Also called:" in embed_products.product_text("611020", MORE["611020"])  # hoodie


async def test_find_from_a_description(
    user: AsyncClient, catalogue: list[int], model: list[str]
) -> None:
    out = await user.post("/api/v1/products/identify", data={"description": "cotton hoodie"})
    assert out.status_code == 200, out.text
    body = out.json()
    assert body["method"] == "ai" and body["semantic"] is True
    assert [p["hs6"] for p in body["picks"]] == ["611020"]  # invented and duplicate dropped
    assert body["picks"][0]["confidence"] == "high" and body["questions"]
    assert "611020" not in [o["hs6"] for o in body["others"]]
    assert "611020: Jerseys, pullovers" in model[-1]  # the alias put it in the candidates


async def test_photo_and_fallbacks(
    user: AsyncClient, catalogue: list[int], model: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    files = {"photo": ("top.png", PNG, "image/png")}
    out = (await user.post("/api/v1/products/identify", files=files)).json()
    assert out["from_photo"] is True and out["query"].startswith("A grey hooded sweatshirt")
    bad = await user.post("/api/v1/products/identify", files={"photo": ("x.gif", b"GIF89a", "")})
    assert bad.status_code == 422 and "JPEG" in bad.json()["detail"]
    assert (
        await user.post("/api/v1/products/identify", data={"description": "x"})
    ).status_code == 422

    def broken(spec: CallSpec, settings: Any = None) -> Any:
        raise RuntimeError("busy")

    async def no_embed(texts: list[str], **_: Any) -> list[list[float]]:
        raise embeddings.EmbeddingError("down")

    monkeypatch.setattr(hs_finder.llm, "get_chat_model", broken)
    monkeypatch.setattr(embeddings, "embed", no_embed)
    plain = (await user.post("/api/v1/products/identify", data={"description": "towels"})).json()
    assert plain["method"] == "search" and plain["semantic"] is False
    assert plain["picks"][0]["hs6"] == "630260" and plain["picks"][0]["confidence"] == "low"


async def test_daily_limit(user: AsyncClient, catalogue: list[int], model: list[str]) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,  # type: ignore[call-arg]
        hs_finder_daily_limit=1,
    )
    try:
        url, body = "/api/v1/products/identify", {"description": "towels"}
        assert (await user.post(url, data=body)).status_code == 200
        assert (await user.post(url, data=body)).status_code == 429
    finally:
        app.dependency_overrides.pop(get_settings, None)
