"""Candidate products for a description: by words, by everyday name, by meaning."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.models.trade import Product, ProductEmbedding

# Every product (not only those with market data): OR of the stemmed words, ranked by
# how many distinct query words the description has, then text rank. Same index
# expression as the product search (PRODUCT_TSVECTOR_SQL).
_WORDS = text("""
    WITH query AS (
        SELECT to_tsvector('english', :q) AS qv,
               replace(plainto_tsquery('english', :q)::text, '&', '|')::tsquery AS tq
    )
    SELECT p.hs6
    FROM ref_product p, query q
    WHERE to_tsvector('english', p.description) @@ q.tq
    ORDER BY cardinality(array(
                SELECT unnest(tsvector_to_array(q.qv))
                INTERSECT SELECT unnest(tsvector_to_array(to_tsvector('english', p.description)))
             )) DESC,
             ts_rank_cd(to_tsvector('english', p.description), q.tq) DESC
    LIMIT :limit
""")


async def by_words(db: AsyncSession, query: str, limit: int) -> list[str]:
    return list((await db.scalars(_WORDS, {"q": query, "limit": limit})).all())


async def by_meaning(db: AsyncSession, vector: list[float], limit: int) -> list[str]:
    """Nearest products by cosine distance (exact scan: ~5,400 rows)."""
    rows = await db.scalars(
        select(ProductEmbedding.hs6)
        .order_by(ProductEmbedding.embedding.cosine_distance(vector))
        .limit(limit)
    )
    return list(rows)


async def by_prefixes(db: AsyncSession, prefixes: Sequence[str]) -> list[str]:
    """Products under the given codes ("6115" -> every 6115xx), in prefix order."""
    if not prefixes:
        return []
    found = list(
        await db.scalars(
            select(Product.hs6).where(or_(*(Product.hs6.startswith(p) for p in prefixes)))
        )
    )
    return [h for p in prefixes for h in sorted(found) if h.startswith(p)]
