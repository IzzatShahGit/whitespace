"""Read queries over the trade tables (loaded by the pipeline)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import Row, and_, case, desc, exists, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from whitespace_api.models.trade import (
    Country,
    MarketOpportunity,
    MarketSupplier,
    Product,
    SupplierLandscape,
)

MarketCountry = aliased(Country, name="market_country")
RivalCountry = aliased(Country, name="rival_country")

# Search works in two modes, chosen by :mode. "sell": products the exporter has ranked
# markets for, strongest first. "buy": products with listed supplier countries, most
# traded first. Each query's `strength` CTE has one branch per mode; the branch whose
# mode doesn't match is a constant-false filter that Postgres skips entirely.
# `n` counts markets (sell) or supplier countries (buy).

# Word search: OR of the stemmed query words, ranked by how many distinct words a
# product contains (`matched` of `wanted`), then text rank, then strength.
# `to_tsvector('english', p.description)` must match the index expression in
# models/trade.py (PRODUCT_TSVECTOR_SQL) so Postgres can use the index.
_WORD_SEARCH = text("""
    WITH query AS (
        SELECT to_tsvector('english', :q) AS qv,
               replace(plainto_tsquery('english', :q)::text, '&', '|')::tsquery AS tq
    ),
    strength AS (
        SELECT hs6, max(exporter_rca) AS strength, count(*) AS n
        FROM gold_market_opportunity WHERE :mode = 'sell' AND exporter = :exporter GROUP BY hs6
        UNION ALL
        SELECT hs6, sum(exports_usd), count(*)
        FROM gold_supplier_landscape WHERE :mode = 'buy' GROUP BY hs6
    )
    SELECT p.hs6, p.description, s.n,
        cardinality(array(
            SELECT unnest(tsvector_to_array(q.qv))
            INTERSECT SELECT unnest(tsvector_to_array(to_tsvector('english', p.description)))
        )) AS matched,
        cardinality(tsvector_to_array(q.qv)) AS wanted
    FROM ref_product p JOIN strength s USING (hs6), query q
    WHERE to_tsvector('english', p.description) @@ q.tq
    ORDER BY matched DESC, ts_rank_cd(to_tsvector('english', p.description), q.tq) DESC,
             s.strength DESC
    LIMIT :limit
""")

# Typo-tolerant fallback when no word matches ("towell", "cottn"). The threshold is
# set high on purpose: trigrams can't fix swapped letters ("towles" scores 0.57 against
# "tomatoes"), and no result is better than a misleading one.
FUZZY_THRESHOLD = 0.65
_FUZZY_SEARCH = text("""
    WITH strength AS (
        SELECT hs6, max(exporter_rca) AS strength, count(*) AS n
        FROM gold_market_opportunity WHERE :mode = 'sell' AND exporter = :exporter GROUP BY hs6
        UNION ALL
        SELECT hs6, sum(exports_usd), count(*)
        FROM gold_supplier_landscape WHERE :mode = 'buy' GROUP BY hs6
    )
    SELECT p.hs6, p.description, s.n, 0 AS matched, 1 AS wanted
    FROM ref_product p JOIN strength s USING (hs6)
    WHERE word_similarity(:q, p.description) >= :threshold
    ORDER BY word_similarity(:q, p.description) DESC, s.strength DESC
    LIMIT :limit
""")

# Code prefix search ("6302" -> every 6302xx product).
_CODE_SEARCH = text("""
    WITH strength AS (
        SELECT hs6, count(*) AS n
        FROM gold_market_opportunity WHERE :mode = 'sell' AND exporter = :exporter GROUP BY hs6
        UNION ALL
        SELECT hs6, count(*)
        FROM gold_supplier_landscape WHERE :mode = 'buy' GROUP BY hs6
    )
    SELECT p.hs6, p.description, s.n, 1 AS matched, 1 AS wanted
    FROM ref_product p JOIN strength s USING (hs6)
    WHERE p.hs6 LIKE :q || '%'
    ORDER BY p.hs6
    LIMIT :limit
""")


async def search_products(
    session: AsyncSession, *, q: str, limit: int, exporter: str | None = None
) -> Sequence[Row[Any]]:
    """Rows of (hs6, description, n, matched, wanted).

    With `exporter`: sell mode (n = ranked markets). Without: buy mode (n = supplier
    countries). `matched` of the `wanted` query words appear in the description.
    """
    params = {"q": q, "limit": limit, "mode": "sell" if exporter else "buy", "exporter": exporter}
    if q.isdigit():
        return (await session.execute(_CODE_SEARCH, params)).all()
    rows = (await session.execute(_WORD_SEARCH, params)).all()
    if rows:
        return rows
    fuzzy = {**params, "threshold": FUZZY_THRESHOLD}
    return (await session.execute(_FUZZY_SEARCH, fuzzy)).all()


async def get_product(session: AsyncSession, hs6: str) -> Product | None:
    return await session.get(Product, hs6)


async def get_country(session: AsyncSession, code: str) -> Country | None:
    return await session.get(Country, code)


async def list_countries(session: AsyncSession) -> Sequence[Country]:
    return (await session.scalars(select(Country).order_by(Country.name))).all()


async def suppliers_for(
    session: AsyncSession, *, market: str, codes: Sequence[str]
) -> list[MarketSupplier]:
    """Who supplies `market` with each of `codes` (one query for many products)."""
    if not codes:
        return []
    rows = await session.scalars(
        select(MarketSupplier).where(MarketSupplier.market == market, MarketSupplier.hs6.in_(codes))
    )
    return list(rows)


async def countries_by_code(session: AsyncSession, codes: Sequence[str]) -> dict[str, Country]:
    if not codes:
        return {}
    rows = await session.scalars(select(Country).where(Country.code.in_(codes)))
    return {c.code: c for c in rows}


async def products_by_code(session: AsyncSession, codes: Sequence[str]) -> dict[str, Product]:
    if not codes:
        return {}
    rows = await session.scalars(select(Product).where(Product.hs6.in_(codes)))
    return {p.hs6: p for p in rows}


async def market_counts(
    session: AsyncSession, *, exporter: str, products: Sequence[str] | None = None
) -> dict[str, int]:
    """Ranked markets per product for an exporter: all its products, or just `products`."""
    if products is not None and not products:
        return {}
    query = (
        select(MarketOpportunity.hs6, func.count())
        .where(MarketOpportunity.exporter == exporter)
        .group_by(MarketOpportunity.hs6)
    )
    if products is not None:
        query = query.where(MarketOpportunity.hs6.in_(products))
    return {hs6: count for hs6, count in (await session.execute(query)).all()}  # noqa: C416


async def best_markets(
    session: AsyncSession, *, exporter: str, products: Sequence[str]
) -> Sequence[Row[Any]]:
    """The rank-1 market of each product, with product details, best first."""
    if not products:
        return []
    query = (
        _opportunities()
        .add_columns(Product.description.label("description"))
        .join(Product, Product.hs6 == MarketOpportunity.hs6)
        .where(
            MarketOpportunity.exporter == exporter,
            MarketOpportunity.hs6.in_(products),
            MarketOpportunity.rank == 1,
        )
        .order_by(MarketOpportunity.score.desc())
    )
    return (await session.execute(query)).all()


async def list_exporters(session: AsyncSession) -> Sequence[Country]:
    covered = exists().where(MarketOpportunity.exporter == Country.code)
    return (await session.scalars(select(Country).where(covered).order_by(Country.name))).all()


async def is_exporter(session: AsyncSession, code: str) -> bool:
    query = select(exists().where(MarketOpportunity.exporter == code))
    return bool(await session.scalar(query))


def _opportunities() -> Any:
    """Opportunity rows with market and rival names, in one query (no N+1)."""
    return (
        select(
            MarketOpportunity,
            MarketCountry.name.label("market_name"),
            RivalCountry.name.label("rival_name"),
        )
        .join(MarketCountry, MarketCountry.code == MarketOpportunity.market)
        .outerjoin(RivalCountry, RivalCountry.code == MarketOpportunity.top_rival)
    )


async def ranked_markets(
    session: AsyncSession, *, exporter: str, hs6: str, limit: int, offset: int
) -> tuple[Sequence[Row[Any]], int]:
    """A page of ranked markets plus the total count (window count: one round trip)."""
    query = (
        _opportunities()
        .add_columns(func.count().over().label("total"))
        .where(MarketOpportunity.exporter == exporter, MarketOpportunity.hs6 == hs6)
        .order_by(MarketOpportunity.rank)
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.execute(query)).all()
    if rows:
        return rows, rows[0].total
    # Past the last page: the window count is unavailable, so count directly.
    total = await session.scalar(
        select(func.count()).where(
            MarketOpportunity.exporter == exporter, MarketOpportunity.hs6 == hs6
        )
    )
    return rows, total or 0


async def top_markets_per_product(
    session: AsyncSession,
    *,
    exporter: str,
    products: Sequence[str],
    exclude_markets: Sequence[str],
    per_product: int,
) -> Sequence[Row[Any]]:
    """The best `per_product` markets for each product, skipping excluded markets.

    One query: a window numbers each product's remaining markets by rank.
    """
    if not products:
        return []
    position = (
        func.row_number()
        .over(partition_by=MarketOpportunity.hs6, order_by=MarketOpportunity.rank)
        .label("position")
    )
    candidates = (
        select(MarketOpportunity.hs6, MarketOpportunity.market, position)
        .where(
            MarketOpportunity.exporter == exporter,
            MarketOpportunity.hs6.in_(products),
            MarketOpportunity.market.not_in(exclude_markets),
        )
        .subquery()
    )
    query = (
        _opportunities()
        .join(
            candidates,
            and_(
                candidates.c.hs6 == MarketOpportunity.hs6,
                candidates.c.market == MarketOpportunity.market,
            ),
        )
        .where(MarketOpportunity.exporter == exporter, candidates.c.position <= per_product)
        .order_by(MarketOpportunity.hs6, MarketOpportunity.rank)
    )
    return (await session.execute(query)).all()


async def get_opportunity(
    session: AsyncSession, *, exporter: str, hs6: str, market: str
) -> Row[Any] | None:
    query = _opportunities().where(
        MarketOpportunity.exporter == exporter,
        MarketOpportunity.hs6 == hs6,
        MarketOpportunity.market == market,
    )
    return (await session.execute(query)).first()


async def market_suppliers(
    session: AsyncSession, *, market: str, hs6: str
) -> Sequence[Row[MarketSupplier, str]]:
    query = (
        select(MarketSupplier, Country.name.label("supplier_name"))
        .join(Country, Country.code == MarketSupplier.supplier)
        .where(MarketSupplier.market == market, MarketSupplier.hs6 == hs6)
        .order_by(MarketSupplier.value_usd.desc())
    )
    return (await session.execute(query)).all()


async def landscape(session: AsyncSession, hs6: str) -> Sequence[Row[SupplierLandscape, str]]:
    """The world's largest exporters of a product, with country names, by rank."""
    query = (
        select(SupplierLandscape, Country.name.label("supplier_name"))
        .join(Country, Country.code == SupplierLandscape.supplier)
        .where(SupplierLandscape.hs6 == hs6)
        .order_by(SupplierLandscape.rank)
    )
    return (await session.execute(query)).all()


async def landscape_counts(
    session: AsyncSession, products: Sequence[str] | None = None
) -> dict[str, int]:
    """Listed supplier countries per product: all products, or just `products`."""
    if products is not None and not products:
        return {}
    query = select(SupplierLandscape.hs6, func.count()).group_by(SupplierLandscape.hs6)
    if products is not None:
        query = query.where(SupplierLandscape.hs6.in_(products))
    return {hs6: count for hs6, count in (await session.execute(query)).all()}  # noqa: C416


async def latest_data_year(session: AsyncSession) -> int | None:
    return await session.scalar(select(func.max(MarketOpportunity.data_year)))


async def related_products(
    session: AsyncSession,
    *,
    exporter: str,
    products: Sequence[str],
    strong_from: float,
    limit: int,
) -> Sequence[Row[Any]]:
    """Other products in the same customs families that `exporter` ranks for.

    Same 4-digit heading first ("close"), then the same 2-digit chapter; within each,
    by how many strong markets they have. Ranked products already passed the
    pipeline's "exports it competitively" test (RCA >= 1), so these are realistic.
    """
    if not products:
        return []
    heading = func.substr(MarketOpportunity.hs6, 1, 4)
    chapter = func.substr(MarketOpportunity.hs6, 1, 2)
    close = func.max(case((heading.in_({p[:4] for p in products}), 1), else_=0)).label("close")
    strong = func.count().filter(MarketOpportunity.score >= strong_from).label("strong")
    query = (
        select(MarketOpportunity.hs6, func.count().label("markets"), strong, close)
        .where(
            MarketOpportunity.exporter == exporter,
            chapter.in_({p[:2] for p in products}),
            MarketOpportunity.hs6.not_in(products),
        )
        .group_by(MarketOpportunity.hs6)
        .having(func.count().filter(MarketOpportunity.score >= strong_from) > 0)
        .order_by(desc("close"), desc("strong"), MarketOpportunity.hs6)
        .limit(limit)
    )
    rows: Sequence[Row[Any]] = (await session.execute(query)).all()
    return rows


async def top_market_rows(
    session: AsyncSession, *, exporter: str, products: Sequence[str]
) -> Sequence[Row[Any]]:
    """The #1 market for each product (with names), in one query."""
    if not products:
        return []
    query = _opportunities().where(
        MarketOpportunity.exporter == exporter,
        MarketOpportunity.hs6.in_(products),
        MarketOpportunity.rank == 1,
    )
    rows: Sequence[Row[Any]] = (await session.execute(query)).all()
    return rows
