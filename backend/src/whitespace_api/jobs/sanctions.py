"""Refresh the sanctions lists: daily in the app's scheduler, or by hand with
`python -m whitespace_api.jobs.sanctions`.

Per list: download to a temp folder (checksummed while streaming); if the checksum is
the one already loaded, only `checked_at` changes. Otherwise the list's names are
replaced in one transaction (delete + batched inserts + source row), so a check never
sees a half-loaded list, and one list failing leaves the others and its own old copy
in place.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import tempfile
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy import delete, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.core import tasks
from whitespace_api.core.config import Settings, get_settings
from whitespace_api.core.names import core_name, norm
from whitespace_api.integrations import sanctions
from whitespace_api.models.screening import SanctionName, SanctionSource

log = logging.getLogger(__name__)
BATCH = 5000
# Bump when parsing or name normalising changes: the checksum then differs, so every list
# is reloaded on the next run even if the files didn't change.
FORMAT_VERSION = b"3"


def rows(source: str, listed: Iterable[sanctions.Listed]) -> Iterable[dict[str, object]]:
    for item in listed:
        core = core_name(item.name) or norm(item.name)
        if len(core) < 2:
            continue
        yield {
            "source": source,
            "ref": item.ref[:40],
            "kind": item.kind,
            "name": item.name[:400],
            "name_core": core[:400],
            "program": (item.program or "")[:300] or None,
            "url": item.url,
        }


async def load(
    db: AsyncSession, source: str, items: Iterable[dict[str, object]], checksum: str
) -> int:
    """Replace one list's names, atomically. Returns how many names were loaded."""
    await db.execute(delete(SanctionName).where(SanctionName.source == source))
    batch: list[dict[str, object]] = []
    total = 0
    parties: set[object] = set()
    for row in items:
        batch.append(row)
        parties.add(row["ref"])
        if len(batch) >= BATCH:
            await db.execute(insert(SanctionName), batch)
            total += len(batch)
            batch = []
    if batch:
        await db.execute(insert(SanctionName), batch)
        total += len(batch)
    now = datetime.now(UTC)
    values = {
        "loaded_at": now,
        "checked_at": now,
        "checksum": checksum,
        "parties": len(parties),
        "names": total,
        "error": None,
    }
    await db.execute(
        pg_insert(SanctionSource)
        .values(source=source, **values)
        .on_conflict_do_update(index_elements=["source"], set_=values)
    )
    await db.commit()
    return total


async def _note(db: AsyncSession, source: str, **values: object) -> None:
    await db.execute(
        pg_insert(SanctionSource)
        .values(source=source, **values)
        .on_conflict_do_update(index_elements=["source"], set_=values)
    )
    await db.commit()


async def refresh(db: AsyncSession, client: httpx.AsyncClient, source: str) -> str:
    spec = sanctions.SOURCES[source]
    digest = hashlib.sha256(FORMAT_VERSION)
    with tempfile.TemporaryDirectory(prefix=f"sanctions-{source}-") as folder:
        paths = [Path(folder) / f"{i}.dat" for i in range(len(spec.files))]
        for url, path in zip(spec.files, paths, strict=True):
            await sanctions.download(client, url, path, digest)
        checksum = digest.hexdigest()
        current = await db.get(SanctionSource, source)
        if current is not None and current.checksum == checksum and current.names > 0:
            await _note(db, source, checked_at=datetime.now(UTC), error=None)
            return f"{source}: unchanged"
        # Parsing is CPU-bound; it runs between awaits of the batched inserts.
        total = await load(db, source, rows(source, sanctions.parse(source, paths)), checksum)
        return f"{source}: {total} names"


async def run(settings: Settings, sources: Iterable[str] | None = None) -> str:
    del settings  # no settings needed; kept for the scheduler's job signature
    out = []
    async with httpx.AsyncClient() as client, tasks.session_factory() as db:
        for source in sources or sanctions.SOURCES:
            try:
                out.append(await refresh(db, client, source))
            except Exception as exc:  # one list down never blocks the others
                await db.rollback()
                log.warning("Sanctions list %s not refreshed: %s", source, exc)
                await _note(db, source, checked_at=datetime.now(UTC), error=str(exc)[:300])
                out.append(f"{source}: failed")
    return ", ".join(out)


async def loaded(db: AsyncSession) -> list[SanctionSource]:
    return list(await db.scalars(select(SanctionSource).order_by(SanctionSource.source)))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(asyncio.run(run(get_settings())))
