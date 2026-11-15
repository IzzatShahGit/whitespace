"""Measured facts for the brief, built from our own data. No model involved.

Each fact is a short line with an id (F1, F2, ...) and pre-formatted figures, so the
writer can copy numbers exactly and the grounding check can find them again.
"""

from __future__ import annotations

from whitespace_api.schemas.brief import BriefFact
from whitespace_api.schemas.trade import MarketDetail, RecentMovement
from whitespace_api.services.explain import EN_DASH, money, percent
from whitespace_shared.niches import NICHES

# Broad words for policy news (tariffs are usually reported per sector, not per product).
_SECTOR_TERMS = {
    "Textiles & apparel": "textile",
    "Food & agriculture": "food",
    "Materials & chemicals": "industrial",
    "Manufactured goods": "manufacturing",
}


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
