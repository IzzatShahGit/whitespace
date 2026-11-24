"""Embed every product for search by description:
`python -m whitespace_api.jobs.embed_products` (after loading new product data).

Only products whose text changed (or that are new) are sent, 100 per request, so a
re-run costs nothing when nothing changed. Products no longer in ref_product are removed.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.core import tasks
from whitespace_api.integrations import embeddings
from whitespace_api.models.trade import Product, ProductEmbedding
from whitespace_shared.aliases import ALIASES

log = logging.getLogger(__name__)


def product_text(hs6: str, description: str) -> str:
    """What gets embedded: the customs wording plus the everyday names people use."""
    names = [name for name, codes in ALIASES.items() if any(hs6.startswith(c) for c in codes)]
    also = f" Also called: {', '.join(names[:8])}." if names else ""
    return f"{description}.{also}"


def text_hash(text: str) -> str:
    return hashlib.sha256(f"{embeddings.MODEL}:{embeddings.DIMENSIONS}:{text}".encode()).hexdigest()


# Free tier, per key: 100 texts a minute and 1,000 a day. One key per batch (the pool
# alternates keys), a pause so each key gets one batch a minute, a full minute's wait
# after a limit hit (retrying sooner only extends it), and a clean stop at the daily cap.
PACE_SECONDS = 31
LIMIT_WAIT_SECONDS = 65
MAX_WAITS = 10


async def _patiently(texts: list[str]) -> list[list[float]]:
    for _ in range(MAX_WAITS):
        try:
            return await embeddings.embed(texts, task="RETRIEVAL_DOCUMENT", attempts=1)
        except embeddings.EmbeddingError as exc:
            if exc.daily_cap:
                raise  # nothing to wait for today; progress so far is saved
            log.info("Rate-limited; waiting %d s", LIMIT_WAIT_SECONDS)
            await asyncio.sleep(LIMIT_WAIT_SECONDS)
    return await embeddings.embed(texts, task="RETRIEVAL_DOCUMENT")


async def run(db: AsyncSession) -> str:
    products = {p.hs6: p.description for p in await db.scalars(select(Product))}
    existing = await db.execute(select(ProductEmbedding.hs6, ProductEmbedding.text_hash))
    stored = {row.hs6: row.text_hash for row in existing}
    texts = {hs6: product_text(hs6, d) for hs6, d in products.items()}
    todo = [hs6 for hs6, t in sorted(texts.items()) if stored.get(hs6) != text_hash(t)]
    gone = set(stored) - set(products)
    if gone:
        await db.execute(delete(ProductEmbedding).where(ProductEmbedding.hs6.in_(gone)))
    for start in range(0, len(todo), embeddings.BATCH):
        batch = todo[start : start + embeddings.BATCH]
        vectors = await _patiently([texts[h] for h in batch])
        rows = [
            {"hs6": h, "embedding": v, "model": embeddings.MODEL, "text_hash": text_hash(texts[h])}
            for h, v in zip(batch, vectors, strict=True)
        ]
        stmt = insert(ProductEmbedding).values(rows)
        await db.execute(
            stmt.on_conflict_do_update(
                index_elements=["hs6"],
                set_={"embedding": stmt.excluded.embedding, "model": stmt.excluded.model,
                      "text_hash": stmt.excluded.text_hash},
            )
        )  # fmt: skip
        await db.commit()  # progress survives an interrupted run
        if start + embeddings.BATCH < len(todo):
            await asyncio.sleep(PACE_SECONDS)
        log.info("Embedded %d/%d products", min(start + embeddings.BATCH, len(todo)), len(todo))
    await db.commit()
    return f"{len(todo)} embedded, {len(products) - len(todo)} unchanged, {len(gone)} removed"


async def main() -> str:
    async with tasks.session_factory() as db:
        try:
            return await run(db)
        except embeddings.EmbeddingError as exc:
            if not exc.daily_cap:
                raise
            done = await db.scalar(select(func.count()).select_from(ProductEmbedding))
            return (
                f"Today's free embedding quota is used up ({done} products done, progress "
                "saved). Run again tomorrow to continue."
            )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(asyncio.run(main()))
