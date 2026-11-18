"""Follow-up reminders: a bell notification when a pipeline follow-up date arrives.

Each reminder's dedupe key is (contact, follow-up date), unique per user, so reruns and
overlapping runs can't repeat one; moving the date creates a fresh reminder.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select

from whitespace_api.core import tasks
from whitespace_api.core.config import Settings
from whitespace_api.models.pipeline import PipelineContact
from whitespace_api.repositories import notifications as notification_repo
from whitespace_api.repositories import trade as trade_repo
from whitespace_api.schemas.pipeline import ACTIVE
from whitespace_api.services.pipeline import STAGE_WORDS, today

BATCH = 500


async def run(settings: Settings, *, on: date | None = None) -> str:
    day = on or today()
    created = 0
    async with tasks.session_factory() as db:
        last_id = None
        while True:
            query = (
                select(PipelineContact)
                .where(PipelineContact.follow_up_on <= day, PipelineContact.stage.in_(ACTIVE))
                .order_by(PipelineContact.id)
                .limit(BATCH)
            )
            if last_id is not None:
                query = query.where(PipelineContact.id > last_id)
            rows = list(await db.scalars(query))
            if not rows:
                break
            last_id = rows[-1].id
            countries = await trade_repo.countries_by_code(db, sorted({r.market for r in rows}))
            notes = []
            for r in rows:
                assert r.follow_up_on is not None
                where = countries[r.market].name if r.market in countries else r.market
                notes.append(
                    {
                        "user_id": r.user_id,
                        "kind": "follow_up",
                        "title": f"Follow up with {r.name}",
                        "body": f"{STAGE_WORDS[r.stage]} · {where}. You planned to check "
                        f"back on {r.follow_up_on:%d %b}.",
                        "link": f"/app/pipeline?contact={r.id}",
                        "data": {"tone": "neutral", "contact_id": str(r.id)},
                        "dedupe_key": f"follow_up:{r.id}:{r.follow_up_on.isoformat()}",
                    }
                )
            created += len(await notification_repo.add_many(db, notes))
            await db.commit()
    return f"{created} follow-up reminders"
