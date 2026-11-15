"""Measured facts for the brief, built from our own data. No model involved.

Each fact is a short line with an id (F1, F2, ...) and pre-formatted figures, so the
writer can copy numbers exactly and the grounding check can find them again.
"""

from __future__ import annotations

import re

from whitespace_api.schemas.brief import BriefFact
from whitespace_api.schemas.trade import MarketDetail, RecentMovement
from whitespace_api.services.explain import EN_DASH, money, percent
from whitespace_shared.aliases import ALIASES
from whitespace_shared.niches import NICHES


def short_product(description: str) -> str:
    """Readable product name: "Bed linen: of cotton (...)" -> "Bed linen of cotton"."""
    head, _, detail = description.partition(": ")
    if not detail:
        name = head
    elif re.match(r"^(of|from|for|in|with|without|not)\b", detail) or detail.startswith("("):
        name = f"{head} {detail}"
    elif len(detail.split()) <= 2:
        name = f"{head}, {detail}"
    else:
        name = detail
    return re.sub(r"\s*\([^)]*\)", "", name).strip()


# Uncountable names that don't take a plural "s" in a search phrase.
_UNCOUNTABLE = {"rice", "salt", "tea", "coffee", "fish", "seafood", "furniture", "cement",
                "marble", "granite", "honey", "beef", "mutton", "chicken", "denim", "footwear",
                "sportswear", "workwear", "packaging", "cutlery", "medicine"}  # fmt: skip
# Broad words for policy news (tariffs are usually reported per sector, not per product).
_SECTOR_TERMS = {
    "Textiles & apparel": "textile",
    "Food & agriculture": "food",
    "Materials & chemicals": "industrial",
    "Manufactured goods": "manufacturing",
}


def everyday_name(hs6: str, description: str) -> str:
    """What people call the product: 630260 -> "towels", 950662 -> "footballs".

    Uses the everyday-name dictionary (most specific code wins), then the niche name,
    then a short form of the official description.
    """
    # Preference: the most specific code, then names that point only at this product
    # ("football" over the generic "ball"), then the more common name (listed first).
    matches = [
        (len(code), -len(codes), -index, alias)
        for index, (alias, codes) in enumerate(ALIASES.items())
        for code in codes
        if hs6.startswith(code)
    ]
    if matches:
        alias = max(matches)[-1]
        last = alias.split()[-1]
        return alias if last in _UNCOUNTABLE or last.endswith("s") else f"{alias}s"
    niche = next((n for n in NICHES if n.matches(hs6)), None)
    if niche:
        return niche.name.lower()
    words = re.findall(r"[A-Za-z][A-Za-z-]+", short_product(description))
    return " ".join(words[:4]).lower()


def sector_term(hs6: str, fallback: str) -> str:
    niche = next((n for n in NICHES if n.matches(hs6)), None)
    return _SECTOR_TERMS.get(niche.sector, fallback) if niche else fallback


def build_facts(detail: MarketDetail, recent: RecentMovement | None) -> list[BriefFact]:
    m, data, exporter = detail.market, detail.data, detail.exporter.name
    years = f"{data.start_year}{EN_DASH}{data.end_year}"
    share = "under 1%" if 0 < m.exporter_share < 0.01 else percent(m.exporter_share)
    rows: list[tuple[str, str]] = [
        (f"Market imports, {data.end_year}", money(m.market_imports_usd)),
        (f"Import growth per year, {years}", percent(m.import_growth_3y)),
        (f"{exporter}'s share of the market, {data.end_year}", share),
    ]
    if m.top_rival:
        rival = m.top_rival.name
        if m.top_rival_share is not None:
            rows.append(
                (f"Main competitor {rival}'s share, {data.end_year}", percent(m.top_rival_share))
            )
        if m.top_rival_share_change is not None:
            change = round(m.top_rival_share_change * 100)
            moved = (
                "little changed"
                if change == 0
                else f"{'fell' if change < 0 else 'rose'} {abs(change)} points"
            )
            rows.append((f"{rival}'s share since {data.start_year}", moved))
    if detail.suppliers:
        top = ", ".join(f"{s.country.name} {percent(s.share_end)}" for s in detail.suppliers[:4])
        rows.append((f"Largest suppliers, {data.end_year}", top))
    rows.append(("Whitespace verdict (rule-based)", f"{m.verdict.headline}. {m.verdict.summary}"))
    if recent is not None and recent.change_12m is not None:
        rows.append(
            (
                f"Monthly data to {recent.latest_month} ({recent.source})",
                f"imports {percent(recent.change_12m)} vs the year before; "
                f"{exporter}'s share {percent(recent.exporter_share_recent)}",
            )
        )
    return [
        BriefFact(id=f"F{i}", label=label, value=value) for i, (label, value) in enumerate(rows, 1)
    ]
