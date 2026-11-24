"""How accurate is the HS code finder? `python -m whitespace_api.tools.eval_hs [--pick]`

Scores each stage on backend/evals/hs_codes.jsonl (description -> accepted codes):
top-1 and top-3 hit rates for words only, everyday names + words, meaning only, the
fused candidate list, and (with --pick, one model call per case) the final picks.
Queries are embedded in one batch, so a run costs one embedding request.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from whitespace_api.core import tasks
from whitespace_api.core.config import get_settings
from whitespace_api.integrations import embeddings
from whitespace_api.repositories import hs as repo
from whitespace_api.repositories import trade as trade_repo
from whitespace_api.services import hs_finder
from whitespace_shared.aliases import codes_for

EVAL_FILE = Path(__file__).resolve().parents[3] / "evals" / "hs_codes.jsonl"


def score(ranked: list[list[str]], wanted: list[list[str]]) -> str:
    n = len(wanted)
    top1 = sum(bool(r[:1]) and r[0] in w for r, w in zip(ranked, wanted, strict=True))
    top3 = sum(any(c in w for c in r[:3]) for r, w in zip(ranked, wanted, strict=True))
    return f"top-1 {top1 / n:6.1%}   top-3 {top3 / n:6.1%}"


# Weightings to compare: (names, words, meaning).
TRY_WEIGHTS: list[tuple[float, ...]] = [
    (1.0, 1.0, 1.0),
    (1.0, 0.5, 2.0),
    (1.0, 0.25, 3.0),
    (0.5, 0.25, 3.0),
]


def within(ranked: list[list[str]], wanted: list[list[str]], n: int = 15) -> str:
    """How often the right code is in the shortlist the model chooses from."""
    hits = sum(any(c in w for c in r[:n]) for r, w in zip(ranked, wanted, strict=True))
    return f"{hits / len(wanted):6.1%}"


async def main(pick: bool) -> None:
    cases = [json.loads(line) for line in EVAL_FILE.read_text().splitlines() if line.strip()]
    queries = [c["q"] for c in cases]
    wanted = [c["hs6"] for c in cases]
    vectors = await embeddings.embed(queries, task="RETRIEVAL_QUERY")
    stages: dict[str, list[list[str]]] = {k: [] for k in ("words", "names+words", "meaning",
                                                          "fused")}  # fmt: skip
    tried: dict[tuple[float, ...], list[list[str]]] = {w: [] for w in TRY_WEIGHTS}
    picks: list[list[str]] = []
    misses = []
    async with tasks.session_factory() as db:
        for q, vector, w in zip(queries, vectors, wanted, strict=True):
            named = await repo.by_prefixes(db, codes_for(q))
            worded = await repo.by_words(db, q, hs_finder.PER_SEARCH)
            meant = await repo.by_meaning(db, vector, hs_finder.PER_SEARCH)
            fused = hs_finder.fuse(
                named[: hs_finder.PER_SEARCH], worded, meant, weights=hs_finder.WEIGHTS
            )
            for weighting in TRY_WEIGHTS:
                tried[weighting].append(
                    hs_finder.fuse(named[: hs_finder.PER_SEARCH], worded, meant, weights=weighting)
                )
            stages["words"].append(worded)
            stages["names+words"].append(hs_finder.fuse(named, worded))
            stages["meaning"].append(meant)
            stages["fused"].append(fused)
            if pick:
                options = fused[: hs_finder.CANDIDATES]
                products = await trade_repo.products_by_code(db, options)
                chosen = await hs_finder.choose(
                    get_settings(), q, {h: products[h].description for h in options}
                )
                picks.append([h for h, _, _ in chosen[0]] if chosen else options[:3])
                if not picks[-1][:1] or picks[-1][0] not in w:
                    misses.append(f"  {q!r}: wanted {w}, got {picks[-1][:3]}")
    print(f"{len(cases)} cases")
    for name, ranked in stages.items():
        print(f"{name:12} {score(ranked, wanted)}")
    for tried_weights, ranked in tried.items():
        print(
            f"fused {tried_weights}  {score(ranked, wanted)}   in top-15 {within(ranked, wanted)}"
        )
    if pick:
        print(f"{'model pick':12} {score(picks, wanted)}")
        print("Top-1 misses:\n" + "\n".join(misses) if misses else "No top-1 misses.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pick", action="store_true", help="also score the model's picks")
    asyncio.run(main(parser.parse_args().pick))
