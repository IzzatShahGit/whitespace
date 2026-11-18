"""Tell users about new open tenders for their products (bell + weekly digest).

Each product is fetched once per run however many users have it; each tender reaches
each user once (dedupe key per tender), and only recent ones, a few per product.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select

from whitespace_api.core import tasks
from whitespace_api.core.config import Settings
from whitespace_api.core.http import http_client
from whitespace_api.models.profile import UserProfile
from whitespace_api.repositories import notifications as notification_repo
from whitespace_api.services import tenders as service

RECENT = timedelta(days=7)
PER_PRODUCT = 3
MAX_PRODUCTS = 200


async def run(settings: Settings, *, today: date | None = None) -> str:
    day = today or datetime.now(UTC).date()
    created = products = 0
    async with tasks.session_factory() as db:
        wanted = list(
            await db.scalars(
                select(func.unnest(UserProfile.products)).distinct().limit(MAX_PRODUCTS)
            )
        )
        for hs6 in sorted(wanted):
            try:
                found, _, stale, name = await service.for_product(db, http_client(), hs6)
            except (service.NotFoundError, service.UnavailableError):
                continue
            products += 1
            recent = [t for t in found if t.published and day - t.published <= RECENT]
            if stale or not recent:
                continue
            users = list(
                await db.scalars(select(UserProfile.user_id).where(UserProfile.products.any(hs6)))
            )
            rows = [
                {
                    "user_id": user_id,
                    "kind": "tender",
                    "title": f"Tender: {t.title[:150]}",
                    "body": f"{t.buyer} ({', '.join(t.country_names)}) is buying {name}. "
                    + (f"Bids close {t.deadline:%d %b %Y}." if t.deadline else ""),
                    "link": "/app/tenders",
                    "data": {"tone": "positive", "number": t.number, "url": t.url},
                    "dedupe_key": f"tender:{t.number}",
                }
                for user_id in users
                for t in recent[:PER_PRODUCT]
            ]
            created += len(await notification_repo.add_many(db, rows))
            await db.commit()
    return f"{products} products checked, {created} tender alerts"
