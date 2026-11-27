"""The admin side: who has an account, what they do, who visits, and account actions.

"Real" accounts exclude test, demo and admin accounts (see analytics.internal_users).
Counts only: admins never see conversation text, emails written or passwords.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.core.config import Settings
from whitespace_api.models.analytics import Visit, VisitPage
from whitespace_api.models.brief import MarketBrief
from whitespace_api.models.chat import ChatMessage, ChatThread
from whitespace_api.models.lead import TradeLeads
from whitespace_api.models.pipeline import PipelineContact
from whitespace_api.models.profile import UserProfile
from whitespace_api.models.quotes import Quote
from whitespace_api.models.requirements import RequirementCheck
from whitespace_api.models.shipments import Shipment
from whitespace_api.models.trade import Country, Product
from whitespace_api.models.usage import UsageCounter
from whitespace_api.models.user import AdminAction, RefreshToken, User, UserActivityDay
from whitespace_api.models.watch import Watch
from whitespace_api.repositories import users as users_repo
from whitespace_api.schemas.admin import (
    AdminActionOut,
    Named,
    ProfileInfo,
    Segment,
    SegmentCounts,
    UserDetail,
    UserFilter,
    UserList,
    UserRow,
    UserSort,
    UserUpdate,
    VisitFilter,
    VisitList,
    VisitOut,
    VisitPageOut,
    VisitUser,
)
from whitespace_api.schemas.analytics import Count
from whitespace_api.services.analytics import internal_users

PER_PAGE = 50
VISITS_PER_PAGE = 30
LIVE = timedelta(minutes=5)  # "on the site now"
FEATURES = {  # usage_counters.kind -> what people did
    "chat": "Questions to the guide",
    "hs": "HS code searches",
    "check": "Buyer checks",
    "doc": "Document checks",
    "intro": "Intro emails written",
}


class AdminError(Exception):
    """An action the admin can't take. The message is safe to show."""


def _sign_in(user: User) -> Literal["google", "password", "both"]:
    if user.google_sub and user.password_hash:
        return "both"
    return "google" if user.google_sub else "password"


def _since_30() -> tuple[date, datetime]:
    day = datetime.now(UTC).date() - timedelta(days=29)
    return day, datetime.combine(day, datetime.min.time(), tzinfo=UTC)


def _per_user_columns() -> tuple[list[Any], list[tuple[Any, Any]]]:
    """Columns for a user row, and the outer joins that feed them."""
    day, start = _since_30()
    active = (
        select(UserActivityDay.user_id, func.count().label("n"))
        .where(UserActivityDay.day >= day)
        .group_by(UserActivityDay.user_id)
        .subquery()
    )
    uses = (
        select(UsageCounter.user_id, func.sum(UsageCounter.count).label("n"))
        .where(UsageCounter.day >= day)
        .group_by(UsageCounter.user_id)
        .subquery()
    )
    seen = (
        select(
            Visit.user_id,
            func.count().label("n"),
            func.sum(Visit.engaged_seconds).label("secs"),
        )
        .where(Visit.user_id.is_not(None), Visit.started_at >= start)
        .group_by(Visit.user_id)
        .subquery()
    )
    latest = (
        select(Visit.user_id, Visit.country)
        .ext(distinct_on(Visit.user_id))
        .where(Visit.user_id.is_not(None), Visit.country.is_not(None))
        .order_by(Visit.user_id, Visit.started_at.desc())
        .subquery()
    )
    first = (
        select(Visit.user_id, Visit.source)
        .ext(distinct_on(Visit.user_id))
        .where(Visit.user_id.is_not(None))
        .order_by(Visit.user_id, Visit.started_at)
        .subquery()
    )
    columns = [
        UserProfile.exporter,
        UserProfile.goal,
        func.coalesce(active.c.n, 0).label("active_days"),
        func.coalesce(uses.c.n, 0).label("feature_uses"),
        func.coalesce(seen.c.n, 0).label("visits"),
        func.coalesce(seen.c.secs, 0).label("engaged"),
        latest.c.country,
        first.c.source,
    ]
    joins = [
        (UserProfile, UserProfile.user_id == User.id),
        (active, active.c.user_id == User.id),
        (uses, uses.c.user_id == User.id),
        (seen, seen.c.user_id == User.id),
        (latest, latest.c.user_id == User.id),
        (first, first.c.user_id == User.id),
    ]
    return columns, joins


def _row(user: User, extra: Any, settings: Settings) -> UserRow:
    return UserRow(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        sign_in=_sign_in(user),
        email_verified=user.email_verified,
        is_active=user.is_active,
        is_test=user.is_test,
        is_admin=settings.is_admin(user.email),
        exporter=extra.exporter,
        goal=extra.goal,
        created_at=user.created_at,
        last_seen_at=user.last_seen_at,
        active_days=int(extra.active_days),
        feature_uses=int(extra.feature_uses),
        visits=int(extra.visits),
        engaged_seconds=int(extra.engaged),
        country=extra.country,
        source=extra.source,
    )


def _user_query(settings: Settings) -> Any:
    columns, joins = _per_user_columns()
    query = select(User, *columns)
    for target, on in joins:
        query = query.outerjoin(target, on)
    return query


async def list_users(
    db: AsyncSession,
    settings: Settings,
    *,
    q: str = "",
    segment: Segment = "real",
    status: UserFilter = "any",
    sort: UserSort = "joined",
    page: int = 1,
) -> UserList:
    internal = internal_users(settings)
    where: list[Any] = []
    if segment == "real":
        where.append(~internal)
    elif segment == "test":
        where.append(internal)
    if q.strip():
        like = f"%{q.strip().lower()}%"
        where.append(or_(User.email.ilike(like), func.lower(User.full_name).like(like)))
    week_ago = datetime.now(UTC) - timedelta(days=7)
    if status == "active":
        where.append(User.last_seen_at >= week_ago)
    elif status == "inactive":
        where.append(or_(User.last_seen_at.is_(None), User.last_seen_at < week_ago))
    elif status == "disabled":
        where.append(User.is_active.is_(False))
    elif status == "unverified":
        where.append(User.email_verified.is_(False))
    elif status == "no_profile":
        where.append(~select(UserProfile.user_id).where(UserProfile.user_id == User.id).exists())

    query = _user_query(settings).where(*where)
    orders: dict[str, list[Any]] = {
        "joined": [User.created_at.desc()],
        "last_seen": [User.last_seen_at.desc().nulls_last()],
        "most_active": [
            query.selected_columns.active_days.desc(),
            User.last_seen_at.desc().nulls_last(),
        ],
        "name": [func.lower(User.full_name)],
    }
    order = orders[sort]
    page = max(page, 1)
    rows = await db.execute(
        query.order_by(*order, User.id).limit(PER_PAGE).offset((page - 1) * PER_PAGE)
    )
    total = await db.scalar(select(func.count()).select_from(User).where(*where))
    counts = (
        await db.execute(
            select(
                func.count().filter(~internal),
                func.count().filter(internal),
                func.count().filter(User.is_active.is_(False)),
            ).select_from(User)
        )
    ).one()
    return UserList(
        total=int(total or 0),
        page=page,
        per_page=PER_PAGE,
        counts=SegmentCounts(real=counts[0], test=counts[1], disabled=counts[2]),
        users=[_row(r[0], r, settings) for r in rows.all()],
    )


def _visit_out(visit: Visit, user: User | None, pages: list[VisitPage]) -> VisitOut:
    return VisitOut(
        id=visit.id,
        started_at=visit.started_at,
        last_seen_at=visit.last_seen_at,
        country=visit.country,
        source=visit.source,
        referrer=visit.referrer,
        utm_campaign=visit.utm_campaign,
        landing=visit.landing,
        device=visit.device,
        browser=visit.browser,
        os=visit.os,
        pages=visit.pages,
        engaged_seconds=visit.engaged_seconds,
        live=visit.last_seen_at >= datetime.now(UTC) - LIVE,
        user=VisitUser(id=user.id, full_name=user.full_name, email=user.email, is_test=user.is_test)
        if user
        else None,
        journey=[VisitPageOut(path=p.path, at=p.at, seconds=p.seconds) for p in pages],
    )


async def _visits_with_pages(db: AsyncSession, query: Any) -> list[VisitOut]:
    rows = (await db.execute(query)).all()
    ids = [visit.id for visit, _ in rows]
    pages: dict[uuid.UUID, list[VisitPage]] = {i: [] for i in ids}
    if ids:
        found = await db.scalars(
            select(VisitPage).where(VisitPage.visit_id.in_(ids)).order_by(VisitPage.at)
        )
        for page in found:
            pages[page.visit_id].append(page)
    return [_visit_out(visit, user, pages[visit.id]) for visit, user in rows]


async def list_visits(
    db: AsyncSession,
    settings: Settings,
    *,
    show: VisitFilter = "all",
    country: str | None = None,
    source: str | None = None,
    include_test: bool = False,
    page: int = 1,
) -> VisitList:
    where: list[Any] = []
    if show == "anonymous":
        where.append(Visit.user_id.is_(None))
    elif show == "signed_in":
        where.append(Visit.user_id.is_not(None))
    if country:
        where.append(Visit.country == country.upper()[:2])
    if source:
        where.append(Visit.source == source)
    if not include_test:
        where.append(
            or_(
                Visit.user_id.is_(None),
                Visit.user_id.not_in(select(User.id).where(internal_users(settings))),
            )
        )
    page = max(page, 1)
    query = (
        select(Visit, User)
        .outerjoin(User, User.id == Visit.user_id)
        .where(*where)
        .order_by(Visit.last_seen_at.desc())
        .limit(VISITS_PER_PAGE)
        .offset((page - 1) * VISITS_PER_PAGE)
    )
    total = await db.scalar(select(func.count()).select_from(Visit).where(*where))
    live = await db.scalar(
        select(func.count()).where(Visit.last_seen_at >= datetime.now(UTC) - LIVE, *where)
    )
    return VisitList(
        total=int(total or 0),
        page=page,
        per_page=VISITS_PER_PAGE,
        live_now=int(live or 0),
        visits=await _visits_with_pages(db, query),
    )


async def _names(db: AsyncSession, key: Any, label: Any, codes: list[str]) -> list[Named]:
    if not codes:
        return []
    found: dict[str, str] = dict((await db.execute(select(key, label).where(key.in_(codes)))).all())
    return [Named(code=c, name=found.get(c, c)) for c in codes]


async def _count(db: AsyncSession, query: Any) -> int:
    return int(await db.scalar(query) or 0)


async def user_detail(
    db: AsyncSession, settings: Settings, user_id: uuid.UUID
) -> UserDetail | None:
    row = (await db.execute(_user_query(settings).where(User.id == user_id))).first()
    if row is None:
        return None
    user: User = row[0]
    now = datetime.now(UTC)
    day30, _ = _since_30()

    profile = await db.get(UserProfile, user_id)
    profile_info = None
    if profile is not None:
        exporter = await _names(db, Country.code, Country.name, [profile.exporter])
        profile_info = ProfileInfo(
            exporter=exporter[0],
            role=profile.role,
            goal=profile.goal,
            products=await _names(db, Product.hs6, Product.description, list(profile.products)),
            current_markets=await _names(
                db, Country.code, Country.name, list(profile.current_markets)
            ),
            updated_at=profile.updated_at,
        )

    days = await db.scalars(
        select(UserActivityDay.day)
        .where(
            UserActivityDay.user_id == user_id,
            UserActivityDay.day >= now.date() - timedelta(days=89),
        )
        .order_by(UserActivityDay.day)
    )
    uses = dict(
        (
            await db.execute(
                select(UsageCounter.kind, func.sum(UsageCounter.count))
                .where(UsageCounter.user_id == user_id, UsageCounter.day >= day30)
                .group_by(UsageCounter.kind)
            )
        ).all()
    )
    feature_use = [
        Count(name=label, count=int(uses.get(kind, 0))) for kind, label in FEATURES.items()
    ]

    threads = select(ChatThread.id).where(ChatThread.user_id == user_id)
    made_queries = {
        "Conversations with the guide": select(func.count())
        .select_from(ChatThread)
        .where(ChatThread.user_id == user_id),
        "Questions asked": select(func.count()).where(
            ChatMessage.thread_id.in_(threads), ChatMessage.role == "user"
        ),
        "Markets watched": select(func.count()).where(Watch.user_id == user_id),
        "Companies in pipeline": select(func.count()).where(PipelineContact.user_id == user_id),
        "Quotes": select(func.count()).where(Quote.user_id == user_id),
        "Shipments": select(func.count()).where(Shipment.user_id == user_id),
        "Requirements ticked": select(func.count()).where(RequirementCheck.user_id == user_id),
        "AI briefs started": select(func.count()).where(MarketBrief.requested_by == user_id),
        "Company searches started": select(func.count()).where(TradeLeads.requested_by == user_id),
    }
    made = [Count(name=name, count=await _count(db, q)) for name, q in made_queries.items()]
    stages = await db.execute(
        select(PipelineContact.stage, func.count())
        .where(PipelineContact.user_id == user_id)
        .group_by(PipelineContact.stage)
        .order_by(func.count().desc())
    )
    sessions = await _count(
        db,
        select(func.count()).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        ),
    )
    visits = await _visits_with_pages(
        db,
        select(Visit, User)
        .outerjoin(User, User.id == Visit.user_id)
        .where(Visit.user_id == user_id)
        .order_by(Visit.started_at.desc())
        .limit(20),
    )
    history = await db.scalars(
        select(AdminAction)
        .where(AdminAction.target_id == user_id)
        .order_by(AdminAction.created_at.desc())
        .limit(20)
    )
    return UserDetail(
        user=_row(user, row, settings),
        locale=user.locale,
        digest_enabled=user.digest_enabled,
        last_login_at=user.last_login_at,
        open_sessions=sessions,
        profile=profile_info,
        active_days=list(days),
        feature_use=feature_use,
        made=made,
        pipeline=[Count(name=stage, count=int(n)) for stage, n in stages.all()],
        visits=visits,
        history=[
            AdminActionOut(action=a.action, admin_email=a.admin_email, created_at=a.created_at)
            for a in history
        ],
    )


async def update_user(
    db: AsyncSession, settings: Settings, admin: User, user_id: uuid.UUID, change: UserUpdate
) -> bool:
    """Disable/enable an account or mark it as a test account. False if it doesn't exist."""
    user = await users_repo.get_user(db, user_id)
    if user is None:
        return False
    now = datetime.now(UTC)
    actions: list[str] = []
    if change.is_active is not None and change.is_active != user.is_active:
        if not change.is_active and (user.id == admin.id or settings.is_admin(user.email)):
            raise AdminError("Admin accounts can't be disabled here")
        user.is_active = change.is_active
        if not change.is_active:
            await users_repo.revoke_all_refresh_tokens(db, user.id, now)  # signed out at once
        actions.append("enable" if change.is_active else "disable")
    if change.is_test is not None and change.is_test != user.is_test:
        user.is_test = change.is_test
        actions.append("mark_test" if change.is_test else "mark_real")
    for action in actions:
        db.add(
            AdminAction(
                admin_email=admin.email, action=action, target_id=user.id, target_email=user.email
            )
        )
    await db.commit()
    return True


async def sign_out_everywhere(db: AsyncSession, admin: User, user_id: uuid.UUID) -> bool:
    user = await users_repo.get_user(db, user_id)
    if user is None:
        return False
    await users_repo.revoke_all_refresh_tokens(db, user.id, datetime.now(UTC))
    db.add(
        AdminAction(
            admin_email=admin.email, action="sign_out", target_id=user.id, target_email=user.email
        )
    )
    await db.commit()
    return True
