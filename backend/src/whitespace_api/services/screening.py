"""Screen a name against the official sanctions lists.

Two steps. Postgres finds candidates fast with trigram indexes (whole-name similarity,
or the name appearing inside a longer listed name). Then code grades each candidate:
- strong: the same name, or near-identical (typos, word order, legal form);
- possible: close, or one name contained in the other on distinctive words.
Generic trade words ("trading", "global", ...) never make a match on their own, and a
one-word name must match exactly. A possible match is a prompt to look, never a verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from typing import Literal

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.core.names import core_name, norm
from whitespace_api.integrations.sanctions import SOURCES
from whitespace_api.models.screening import SanctionName, SanctionSource

Grade = Literal["strong", "possible"]
STRONG = 0.92
POSSIBLE = 0.80
RETRIEVE_SIMILARITY = 0.45
RETRIEVE_WORD = 0.7
CANDIDATES = 60
GENERIC = {
    "trading", "trade", "traders", "international", "intl", "global", "group", "holding",
    "holdings", "industries", "industry", "industrial", "import", "export", "imports",
    "exports", "general", "services", "service", "enterprise", "enterprises", "company",
    "commercial", "textile", "textiles", "mills", "foods", "food", "products", "logistics",
    "shipping", "investment", "investments", "development", "al", "el", "de", "and", "of",
    "the", "for", "bank", "national", "united", "new", "world", "star", "royal", "first",
}  # fmt: skip


@dataclass(frozen=True)
class Match:
    source: str
    source_label: str
    ref: str
    name: str
    program: str | None
    url: str | None
    score: float
    grade: Grade


def similarity(a: str, b: str) -> float:
    """0..1 between two comparable names, ignoring word order."""
    if a == b:
        return 1.0
    ordered = SequenceMatcher(None, " ".join(sorted(a.split())), " ".join(sorted(b.split())))
    return max(ordered.ratio(), SequenceMatcher(None, a, b).ratio())


def _distinctive(tokens: set[str]) -> set[str]:
    return {t for t in tokens if t not in GENERIC and len(t) >= 4}


def grade(query: str, candidate: str) -> tuple[float, Grade | None]:
    score = similarity(query, candidate)
    q, c = set(query.split()), set(candidate.split())
    one_word = len(q) == 1 or len(c) == 1
    if query == candidate:
        # "ALFA" alone is too common to call; a long single word is specific enough.
        strong = not one_word or len(query) >= 6
        return 1.0, "strong" if strong and _distinctive(q) else "possible"
    if not _distinctive(q & c):
        return score, None  # sharing only generic words is not a match
    if not one_word and score >= STRONG:
        return score, "strong"
    if not one_word and score >= POSSIBLE:
        return score, "possible"
    small, large = (q, c) if len(q) <= len(c) else (c, q)
    # "rosneft" in "rosneft aero"; but one short word ("alfa") is too weak to raise.
    contained = small <= large and len(large) <= len(small) + 3
    if contained and (len(small) > 1 or len(next(iter(small))) >= 5):
        return score, "possible"
    return score, None


def comparable(name: str) -> str:
    return core_name(name) or norm(name)


async def screen(
    db: AsyncSession, name: str, *, kind: Literal["entity", "individual"] = "entity"
) -> list[Match]:
    """Best match per listed party, strong ones first; empty if nothing is close."""
    query = comparable(name)
    if len(query) < 3:
        return []
    await db.execute(
        text("SELECT set_config('pg_trgm.similarity_threshold', :s, true), "
             "set_config('pg_trgm.word_similarity_threshold', :w, true)"),
        {"s": str(RETRIEVE_SIMILARITY), "w": str(RETRIEVE_WORD)},
    )  # fmt: skip
    rank = func.greatest(
        func.similarity(SanctionName.name_core, query),
        func.word_similarity(query, SanctionName.name_core),
    )
    rows = await db.execute(
        select(SanctionName)
        .where(
            SanctionName.kind == kind,
            or_(
                SanctionName.name_core.op("%")(query),
                text("CAST(:q AS text) <% sanction_names.name_core").bindparams(q=query),
            ),
        )
        .order_by(rank.desc())
        .limit(CANDIDATES)
    )
    best: dict[tuple[str, str], Match] = {}
    for row in rows.scalars():
        score, verdict = grade(query, row.name_core)
        if verdict is None:
            continue
        key = (row.source, row.ref)
        current = best.get(key)
        if current is None or (verdict, score) > (current.grade, current.score):
            best[key] = Match(
                source=row.source,
                source_label=SOURCES[row.source].label if row.source in SOURCES else row.source,
                ref=row.ref,
                name=row.name,
                program=row.program,
                url=row.url,
                score=round(score, 3),
                grade=verdict,
            )
    return sorted(best.values(), key=lambda m: (m.grade != "strong", -m.score))[:6]


@dataclass(frozen=True)
class ListStatus:
    source: str
    label: str
    loaded_at: datetime | None
    names: int
    error: str | None


async def lists(db: AsyncSession) -> list[ListStatus]:
    """Every list we screen against, with when our copy was last loaded."""
    stored = {s.source: s for s in await db.scalars(select(SanctionSource))}
    out = []
    for key, spec in SOURCES.items():
        row = stored.get(key)
        out.append(
            ListStatus(
                source=key,
                label=spec.label,
                loaded_at=row.loaded_at if row else None,
                names=row.names if row else 0,
                error=row.error if row else None,
            )
        )
    return out
