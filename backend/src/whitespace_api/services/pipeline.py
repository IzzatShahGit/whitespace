"""The outreach pipeline: save companies, move them through stages, get reminded.

Concurrency:
- Adding is one INSERT ... ON CONFLICT DO NOTHING on (user, product, market, name):
  double clicks and two tabs keep one row.
- Edits lock just that row (SELECT ... FOR UPDATE), check the version the client saw,
  write the change and its event, and commit: no lost updates, and a single-row lock
  can't deadlock.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.agents.leads import _norm, core_name
from whitespace_api.core.config import Settings
from whitespace_api.models.pipeline import PipelineContact, PipelineEvent
from whitespace_api.models.user import User
from whitespace_api.repositories import trade as trade_repo
from whitespace_api.schemas.pipeline import (
    ACTIVE,
    ContactAdded,
    ContactIn,
    ContactOut,
    ContactPatch,
    EventOut,
    PipelineSummary,
)
from whitespace_shared.naming import everyday_name

FOLLOW_UP_AFTER = timedelta(days=5)  # after an email goes out, check back in five days
STAGE_WORDS = {
    "to_contact": "To contact",
    "emailed": "Emailed",
    "replied": "Replied",
    "samples": "Samples sent",
    "negotiating": "Negotiating",
    "won": "Won",
    "lost": "Closed, no deal",
}


class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    """The contact changed since the client loaded it."""


class LimitError(Exception):
    pass


def today() -> date:
    return datetime.now(UTC).date()


def name_key(name: str) -> str:
    return (core_name(name) or _norm(name))[:160]


async def _out(db: AsyncSession, rows: list[PipelineContact]) -> list[ContactOut]:
    products = await trade_repo.products_by_code(db, sorted({r.hs6 for r in rows}))
    countries = await trade_repo.countries_by_code(db, sorted({r.market for r in rows}))
    now = today()

    def one(r: PipelineContact) -> ContactOut:
        product = products.get(r.hs6)
        return ContactOut(
            id=r.id,
            hs6=r.hs6,
            product_name=everyday_name(r.hs6, product.description) if product else r.hs6,
            market=r.market,
            market_name=countries[r.market].name if r.market in countries else r.market,
            side=r.side,
            name=r.name,
            kind=r.kind,
            city=r.city,
            website=r.website,
            source_url=r.source_url,
            stage=r.stage,
            note=r.note,
            follow_up_on=r.follow_up_on,
            due=r.follow_up_on is not None and r.follow_up_on <= now and r.stage in ACTIVE,
            last_contacted_at=r.last_contacted_at,
            version=r.version,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )

    return [one(r) for r in rows]


async def list_contacts(db: AsyncSession, user: User) -> list[ContactOut]:
    rows = await db.scalars(
        select(PipelineContact)
        .where(PipelineContact.user_id == user.id)
        .order_by(PipelineContact.updated_at.desc())
    )
    return await _out(db, list(rows))


async def add(db: AsyncSession, user: User, body: ContactIn, settings: Settings) -> ContactAdded:
    if await trade_repo.get_product(db, body.hs6) is None:
        raise NotFoundError(f"Unknown product {body.hs6}")
    if body.market not in await trade_repo.countries_by_code(db, [body.market]):
        raise NotFoundError(f"Unknown country {body.market}")
    key = name_key(body.name)
    if len(key) < 2:
        raise NotFoundError("That doesn't look like a company name")
    count = await db.scalar(select(func.count()).where(PipelineContact.user_id == user.id))
    if (count or 0) >= settings.pipeline_limit:
        raise LimitError(
            f"Your pipeline holds up to {settings.pipeline_limit} companies. "
            "Remove closed ones to add more."
        )
    new_id = await db.scalar(
        insert(PipelineContact)
        .values(
            id=uuid.uuid4(),
            user_id=user.id,
            hs6=body.hs6,
            market=body.market,
            side=body.side,
            name=body.name.strip(),
            name_key=key,
            kind=body.kind,
            city=body.city,
            website=body.website,
            source_url=body.source_url,
        )
        .on_conflict_do_nothing(constraint="uq_pipeline_contact")
        .returning(PipelineContact.id)
    )
    if new_id is not None:
        db.add(PipelineEvent(contact_id=new_id, kind="added", detail="Added to your pipeline"))
    await db.commit()
    row = await db.scalar(
        select(PipelineContact).where(
            PipelineContact.user_id == user.id,
            PipelineContact.hs6 == body.hs6,
            PipelineContact.market == body.market,
            PipelineContact.name_key == key,
        )
    )
    assert row is not None
    return ContactAdded(contact=(await _out(db, [row]))[0], created=new_id is not None)


async def update(
    db: AsyncSession, user: User, contact_id: uuid.UUID, body: ContactPatch
) -> ContactOut:
    row = await db.scalar(
        select(PipelineContact)
        .where(PipelineContact.id == contact_id, PipelineContact.user_id == user.id)
        .with_for_update()
    )
    if row is None:
        await db.rollback()
        raise NotFoundError("Not in your pipeline")
    if row.version != body.version:
        await db.rollback()
        raise ConflictError("This company was changed elsewhere. Reload to see the latest.")
    fields = body.model_fields_set
    events: list[tuple[str, str]] = []
    now = datetime.now(UTC)
    stage = body.stage if body.stage is not None else row.stage
    if "note" in fields and ((body.note or "").strip() or None) != row.note:
        row.note = (body.note or "").strip() or None
        events.append(("note", "Note updated"))
    follow_up = body.follow_up_on if "follow_up_on" in fields else row.follow_up_on
    if stage != row.stage:
        events.append(("stage", f"{STAGE_WORDS[row.stage]} → {STAGE_WORDS[stage]}"))
        if stage == "emailed":
            row.last_contacted_at = now
            if "follow_up_on" not in fields and follow_up is None:
                follow_up = today() + FOLLOW_UP_AFTER
        row.stage = stage
    if stage not in ACTIVE:
        follow_up = None  # won or lost: nothing to chase
    if follow_up != row.follow_up_on:
        if "follow_up_on" in fields:  # the user's own change (automatic ones go unlogged)
            events.append(
                ("follow_up", f"Follow up on {follow_up:%d %b %Y}")
                if follow_up
                else ("follow_up", "Follow-up cleared")
            )
        row.follow_up_on = follow_up
    if events:
        row.version += 1
        row.updated_at = now
        db.add_all(PipelineEvent(contact_id=row.id, kind=k, detail=d) for k, d in events)
    await db.commit()
    return (await _out(db, [row]))[0]


async def remove(db: AsyncSession, user: User, contact_id: uuid.UUID) -> None:
    result = await db.execute(
        delete(PipelineContact)
        .where(PipelineContact.id == contact_id, PipelineContact.user_id == user.id)
        .returning(PipelineContact.id)
    )
    await db.commit()
    if result.first() is None:
        raise NotFoundError("Not in your pipeline")


async def events(db: AsyncSession, user: User, contact_id: uuid.UUID) -> list[EventOut]:
    owned = await db.scalar(
        select(PipelineContact.id).where(
            PipelineContact.id == contact_id, PipelineContact.user_id == user.id
        )
    )
    if owned is None:
        raise NotFoundError("Not in your pipeline")
    rows = await db.scalars(
        select(PipelineEvent)
        .where(PipelineEvent.contact_id == contact_id)
        .order_by(PipelineEvent.created_at.desc(), PipelineEvent.id.desc())
        .limit(50)
    )
    return [EventOut(kind=e.kind, detail=e.detail, created_at=e.created_at) for e in rows]


async def summary(db: AsyncSession, user: User) -> PipelineSummary:
    counts = dict(
        (
            await db.execute(
                select(PipelineContact.stage, func.count())
                .where(PipelineContact.user_id == user.id)
                .group_by(PipelineContact.stage)
            )
        ).all()
    )
    due = await db.scalars(
        select(PipelineContact)
        .where(
            PipelineContact.user_id == user.id,
            PipelineContact.follow_up_on <= today(),
            PipelineContact.stage.in_(ACTIVE),
        )
        .order_by(PipelineContact.follow_up_on, PipelineContact.name)
        .limit(20)
    )
    return PipelineSummary(
        total=sum(counts.values()),
        by_stage={stage: counts.get(stage, 0) for stage in STAGE_WORDS},
        due=await _out(db, list(due)),
    )
