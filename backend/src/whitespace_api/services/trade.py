"""Market search use cases: validate the request, query, and shape the answer."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Row
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.repositories import trade as repo
from whitespace_api.schemas.trade import (
    CountryOut,
    DataWindow,
    MarketDetail,
    MarketItem,
    MarketsPage,
    NicheDetail,
    NicheProduct,
    NicheSummary,
    ProductMatch,
    ProductOut,
    SectorOut,
    SupplierOut,
)
from whitespace_api.services import explain
from whitespace_shared.niches import BY_SLUG, NICHES, SECTORS

GROWTH_YEARS = 3  # matches the pipeline's scoring window


class NotFoundError(Exception):
    """The requested exporter, product or market isn't in the data. Safe to show."""


NO_MARKETS: frozenset[str] = frozenset()


async def list_exporters(db: AsyncSession) -> list[CountryOut]:
    return [CountryOut(code=c.code, name=c.name) for c in await repo.list_exporters(db)]


async def list_countries(db: AsyncSession) -> list[CountryOut]:
    return [CountryOut(code=c.code, name=c.name) for c in await repo.list_countries(db)]


async def get_exporter(db: AsyncSession, code: str) -> CountryOut:
    country = await repo.get_country(db, code)
    if country is None or not await repo.is_exporter(db, code):
        raise NotFoundError(f"We don't cover exports from {code} yet")
    return CountryOut(code=country.code, name=country.name)


async def get_product(db: AsyncSession, hs6: str) -> ProductOut:
    product = await repo.get_product(db, hs6)
    if product is None:
        raise NotFoundError(f"Unknown product code {hs6}")
    return ProductOut(hs6=product.hs6, description=product.description)


async def search_products(
    db: AsyncSession, *, q: str, exporter: str, limit: int
) -> list[ProductMatch]:
    await get_exporter(db, exporter)
    rows = await repo.search_products(db, q=q.strip(), exporter=exporter, limit=limit)
    return [ProductMatch(hs6=r.hs6, description=r.description, markets=r.markets) for r in rows]


def data_window(row: Row[Any]) -> DataWindow:
    o = row.MarketOpportunity
    return DataWindow(
        start_year=o.data_year - GROWTH_YEARS, end_year=o.data_year, version=o.data_version
    )


def market_item(
    row: Row[Any], exporter: CountryOut, selling_in: frozenset[str] = NO_MARKETS
) -> MarketItem:
    """One ranked market, explained. `selling_in`: markets the user already sells to."""
    o = row.MarketOpportunity
    facts = explain.Facts(
        exporter_name=exporter.name,
        rival_name=row.rival_name,
        start_year=o.data_year - GROWTH_YEARS,
        end_year=o.data_year,
        market_imports_usd=o.market_imports_usd,
        import_growth_3y=o.import_growth_3y,
        top_rival_share_change=o.top_rival_share_change,
        exporter_share=o.exporter_share,
    )
    return MarketItem(
        rank=o.rank,
        market=CountryOut(code=o.market, name=row.market_name),
        label=explain.label(o.score),
        score=o.score,
        market_imports_usd=o.market_imports_usd,
        import_growth_3y=o.import_growth_3y,
        exporter_share=o.exporter_share,
        top_rival=CountryOut(code=o.top_rival, name=row.rival_name) if o.top_rival else None,
        top_rival_share_change=o.top_rival_share_change,
        reasons=explain.reasons(facts),
        already_selling=o.market in selling_in,
    )


async def ranked_markets(
    db: AsyncSession,
    *,
    exporter: str,
    hs6: str,
    limit: int,
    offset: int,
    selling_in: frozenset[str] = NO_MARKETS,
) -> MarketsPage:
    exp = await get_exporter(db, exporter)
    product = await get_product(db, hs6)
    rows, total = await repo.ranked_markets(
        db, exporter=exporter, hs6=hs6, limit=limit, offset=offset
    )
    return MarketsPage(
        exporter=exp,
        product=product,
        data=data_window(rows[0]) if rows else None,
        total=total,
        limit=limit,
        offset=offset,
        items=[market_item(r, exp, selling_in) for r in rows],
    )


async def market_detail(
    db: AsyncSession,
    *,
    exporter: str,
    hs6: str,
    market: str,
    selling_in: frozenset[str] = NO_MARKETS,
) -> MarketDetail:
    exp = await get_exporter(db, exporter)
    product = await get_product(db, hs6)
    row = await repo.get_opportunity(db, exporter=exporter, hs6=hs6, market=market)
    if row is None:
        raise NotFoundError(f"{market} is not a ranked market for this product")
    suppliers = await repo.market_suppliers(db, market=market, hs6=hs6)
    return MarketDetail(
        exporter=exp,
        product=product,
        data=data_window(row),
        market=market_item(row, exp, selling_in),
        suppliers=[
            SupplierOut(
                country=CountryOut(code=s.MarketSupplier.supplier, name=s.supplier_name),
                value_usd=s.MarketSupplier.value_usd,
                share_start=s.MarketSupplier.share_start,
                share_end=s.MarketSupplier.share_end,
            )
            for s in suppliers
        ],
    )


async def list_niches(db: AsyncSession, *, exporter: str) -> list[SectorOut]:
    """Every niche, grouped by sector, with how many products have ranked markets."""
    await get_exporter(db, exporter)
    products = await repo.market_counts(db, exporter=exporter)
    return [
        SectorOut(
            name=sector,
            niches=[
                NicheSummary(
                    slug=n.slug,
                    name=n.name,
                    products=sum(1 for hs6 in products if n.matches(hs6)),
                )
                for n in NICHES
                if n.sector == sector
            ],
        )
        for sector in SECTORS
    ]


async def niche_detail(
    db: AsyncSession, *, slug: str, exporter: str, selling_in: frozenset[str] = NO_MARKETS
) -> NicheDetail:
    """The niche's products for this exporter, each with its best market, best first."""
    niche = BY_SLUG.get(slug)
    if niche is None:
        raise NotFoundError(f"Unknown niche {slug}")
    exp = await get_exporter(db, exporter)
    counts = await repo.market_counts(db, exporter=exporter)
    in_niche = [hs6 for hs6 in counts if niche.matches(hs6)]
    rows = await repo.best_markets(db, exporter=exporter, products=in_niche)
    return NicheDetail(
        slug=niche.slug,
        name=niche.name,
        sector=niche.sector,
        exporter=exp,
        products=[
            NicheProduct(
                product=ProductOut(hs6=r.MarketOpportunity.hs6, description=r.description),
                markets=counts[r.MarketOpportunity.hs6],
                best=market_item(r, exp, selling_in),
            )
            for r in rows
        ],
    )
