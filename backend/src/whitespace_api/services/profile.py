"""User profile: what someone exports and from where, and the dashboard built on it."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.models.profile import UserProfile
from whitespace_api.models.user import User
from whitespace_api.repositories import profiles as profile_repo
from whitespace_api.repositories import trade as trade_repo
from whitespace_api.schemas.profile import (
    BestMove,
    Dashboard,
    GrowRange,
    ProductOpportunities,
    ProfileIn,
    ProfileOut,
    RangeIdea,
)
from whitespace_api.schemas.trade import CountryOut, MarketItem, ProductOut
from whitespace_api.services import trade as trade_service
from whitespace_api.services.explain import STRONG_FROM

TOP_PER_PRODUCT = 3
BEST_MOVES = 3
# Candidates per product scanned for best moves: deeper than the cards, since the
# top-ranked markets can be ones that are hard to enter.
BEST_MOVE_CANDIDATES = 15
ACTIONABLE = frozenset({"go", "test"})


class NoProfileError(Exception):
    """The user hasn't completed onboarding yet."""


class InvalidProfileError(Exception):
    """The submitted profile doesn't fit the data. The message is safe to show."""


def _unique(codes: list[str]) -> list[str]:
    """Drop duplicates, keep the user's order."""
    return list(dict.fromkeys(codes))


async def _to_out(db: AsyncSession, profile: UserProfile) -> ProfileOut:
    """Attach names. Codes that vanished from a later data release are skipped."""
    countries = await trade_repo.countries_by_code(db, [profile.exporter, *profile.current_markets])
    products = await trade_repo.products_by_code(db, profile.products)
    exporter = countries.get(profile.exporter)
    return ProfileOut(
        exporter=CountryOut(
            code=profile.exporter, name=exporter.name if exporter else profile.exporter
        ),
        role=profile.role,
        goal=profile.goal,
        products=[
            ProductOut(hs6=p.hs6, description=p.description)
            for code in profile.products
            if (p := products.get(code))
        ],
        current_markets=[
            CountryOut(code=c.code, name=c.name)
            for code in profile.current_markets
            if (c := countries.get(code))
        ],
        updated_at=profile.updated_at,
    )


async def _require(db: AsyncSession, user: User) -> UserProfile:
    profile = await profile_repo.get_profile(db, user.id)
    if profile is None:
        raise NoProfileError
    return profile


async def get_profile(db: AsyncSession, user: User) -> ProfileOut:
    return await _to_out(db, await _require(db, user))


async def save_profile(db: AsyncSession, user: User, body: ProfileIn) -> ProfileOut:
    try:
        await trade_service.get_exporter(db, body.exporter)
    except trade_service.NotFoundError as exc:
        raise InvalidProfileError(str(exc)) from exc

    products = _unique(body.products)
    if body.goal == "buy":  # buyers need suppliers listed; sellers need ranked markets
        available = await trade_repo.landscape_counts(db, products)
        problem = "No supplier data for product(s)"
    else:
        available = await trade_repo.market_counts(db, exporter=body.exporter, products=products)
        problem = f"No ranked markets from {body.exporter} for product(s)"
    missing = [code for code in products if code not in available]
    if missing:
        raise InvalidProfileError(f"{problem} {', '.join(missing)}")

    markets = [m for m in _unique(body.current_markets) if m != body.exporter]
    known = await trade_repo.countries_by_code(db, markets)
    unknown = [m for m in markets if m not in known]
    if unknown:
        raise InvalidProfileError(f"Unknown country code(s) {', '.join(unknown)}")

    profile = await profile_repo.upsert_profile(
        db,
        user_id=user.id,
        exporter=body.exporter,
        role=body.role,
        goal=body.goal,
        products=products,
        current_markets=markets,
    )
    return await _to_out(db, profile)


async def selling_in(db: AsyncSession, user: User, exporter: str) -> frozenset[str]:
    """Markets the user sells to, when browsing their own country's exports.

    An advisor looking at another country's exports gets no flags: their markets
    belong to their own business, not to that country.
    """
    profile = await profile_repo.get_profile(db, user.id)
    if profile is None or profile.exporter != exporter:
        return trade_service.NO_MARKETS
    return frozenset(profile.current_markets)


async def dashboard(db: AsyncSession, user: User) -> Dashboard:
    """Best new markets per product, plus the best actionable moves across products."""
    profile = await _require(db, user)
    out = await _to_out(db, profile)
    product_codes = [p.hs6 for p in out.products]
    names = {p.hs6: p for p in out.products}
    counts = await trade_repo.market_counts(db, exporter=profile.exporter, products=product_codes)
    rows = await trade_repo.top_markets_per_product(
        db,
        exporter=profile.exporter,
        products=product_codes,
        exclude_markets=profile.current_markets,
        per_product=BEST_MOVE_CANDIDATES,
    )
    top: dict[str, list[MarketItem]] = {code: [] for code in product_codes}
    candidates: list[BestMove] = []
    for row in rows:
        item = trade_service.market_item(row, out.exporter)
        hs6 = row.MarketOpportunity.hs6
        if len(top[hs6]) < TOP_PER_PRODUCT:
            top[hs6].append(item)
        if item.verdict.action in ACTIONABLE:
            candidates.append(BestMove(product=names[hs6], market=item))
    best = sorted(candidates, key=lambda m: m.market.score, reverse=True)[:BEST_MOVES]
    return Dashboard(
        profile=out,
        data=trade_service.data_window(rows[0]) if rows else None,
        best_moves=best,
        products=[
            ProductOpportunities(product=p, total_markets=counts.get(p.hs6, 0), top=top[p.hs6])
            for p in out.products
        ],
    )


RANGE_IDEAS = 6


async def grow_range(db: AsyncSession, user: User) -> GrowRange:
    """Products to add next: close relatives of what the user sells, with strong markets."""
    profile = await _require(db, user)
    rows = await trade_repo.related_products(
        db,
        exporter=profile.exporter,
        products=profile.products,
        strong_from=STRONG_FROM,
        limit=RANGE_IDEAS,
    )
    codes = [r.hs6 for r in rows]
    names = await trade_repo.products_by_code(db, codes)
    tops = {
        r.MarketOpportunity.hs6: r
        for r in await trade_repo.top_market_rows(db, exporter=profile.exporter, products=codes)
    }
    exporter = await trade_service.get_exporter(db, profile.exporter)
    selling = frozenset(profile.current_markets)
    return GrowRange(
        ideas=[
            RangeIdea(
                product=ProductOut(hs6=r.hs6, description=names[r.hs6].description),
                same_family=bool(r.close),
                markets=r.markets,
                strong_markets=r.strong,
                top=trade_service.market_item(tops[r.hs6], exporter, selling),
            )
            for r in rows
            if r.hs6 in names and r.hs6 in tops
        ]
    )
