"""Turn a scored market into advice: signals, a verdict, and plain-language reasons.

Pure functions over numbers that came from the database: nothing is invented, the
same row always produces the same words, and every signal states the figure behind
it. All thresholds live here, named, so the rules can be reviewed and tuned in one place.
"""

from __future__ import annotations

from dataclasses import dataclass

from whitespace_api.schemas.trade import Action, Label, Signal, Tone, Verdict

EN_DASH = "\u2013"  # typographic dash for year ranges (2021 to 2024)

# ---------- thresholds ----------
# Opportunity score -> label
STRONG_FROM = 0.70
GOOD_FROM = 0.55
# Changes smaller than this read as "steady"
STEADY_WITHIN = 0.005
# Demand: compound annual import growth
FAST_GROWTH = 0.08
GROWTH = 0.02
SHRINKING = -0.02
# Competition: the main rival's share and its change (in share points, 0.05 = 5 pts)
DOMINANT_SHARE = 0.60
RIVAL_LOSING = -0.05
RIVAL_SLIPPING = -0.01
RIVAL_GAINING = 0.01
# The exporter's own position
UNTAPPED = 0.01
ESTABLISHED = 0.15
LEADING = 0.35
# Market size (USD, last year)
VERY_LARGE = 500e6
LARGE = 100e6
MID_SIZE = 25e6


@dataclass(frozen=True)
class Facts:
    exporter_name: str
    rival_name: str | None
    start_year: int
    end_year: int
    market_imports_usd: float
    import_growth_3y: float
    top_rival_share_change: float | None
    exporter_share: float
    top_rival_share: float | None = None


def label(score: float) -> Label:
    if score >= STRONG_FROM:
        return "Strong"
    if score >= GOOD_FROM:
        return "Good"
    return "Watch"


def percent(value: float) -> str:
    return f"{value * 100:.0f}%"


def money(usd: float) -> str:
    for unit, size in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if usd >= size:
            amount = usd / size
            return f"${amount:.1f}{unit}" if amount < 10 else f"${amount:.0f}{unit}"
    return f"${usd:.0f}"


def _points(change: float) -> str:
    return f"{abs(change) * 100:.0f} points"


# ---------- signals ----------
def demand_signal(f: Facts) -> Signal:
    g, years = f.import_growth_3y, f"{f.start_year}{EN_DASH}{f.end_year}"
    if g >= FAST_GROWTH:
        return Signal(
            kind="demand",
            tone="positive",
            title="Fast-growing demand",
            detail=f"Imports grew {percent(g)} a year, {years}",
        )
    if g >= GROWTH:
        return Signal(
            kind="demand",
            tone="positive",
            title="Growing demand",
            detail=f"Imports grew {percent(g)} a year, {years}",
        )
    if g > SHRINKING:
        return Signal(
            kind="demand",
            tone="neutral",
            title="Stable demand",
            detail=f"Imports changed {percent(g)} a year, {years}",
        )
    return Signal(
        kind="demand",
        tone="negative",
        title="Shrinking demand",
        detail=f"Imports fell {percent(-g)} a year, {years}",
    )


def _dominated(f: Facts) -> bool:
    change = f.top_rival_share_change or 0.0
    return (f.top_rival_share or 0.0) >= DOMINANT_SHARE and change > RIVAL_LOSING


def competition_signal(f: Facts) -> Signal:
    rival, change, share = f.rival_name, f.top_rival_share_change, f.top_rival_share
    if rival is None or change is None:
        return Signal(
            kind="competition",
            tone="neutral",
            title="No major competitor",
            detail="No other supplier stood out",
        )
    since = f"since {f.start_year}"
    if _dominated(f):
        return Signal(
            kind="competition",
            tone="negative",
            title=f"Dominated by {rival}",
            detail=f"{rival} supplies {percent(share or 0)} of imports",
        )
    if change <= RIVAL_LOSING:
        return Signal(
            kind="competition",
            tone="positive",
            title="Competitor losing ground",
            detail=f"{rival}'s share fell {_points(change)} {since}",
        )
    if change <= RIVAL_SLIPPING:
        return Signal(
            kind="competition",
            tone="positive",
            title="Competitor slipping",
            detail=f"{rival}'s share fell {_points(change)} {since}",
        )
    if change >= RIVAL_GAINING:
        return Signal(
            kind="competition",
            tone="negative",
            title="Competitor gaining",
            detail=f"{rival} gained {_points(change)} of share {since}",
        )
    held = f"{rival} holds {percent(share)}" if share is not None else f"{rival}'s share"
    return Signal(
        kind="competition",
        tone="neutral",
        title="Competition steady",
        detail=f"{held}, little changed {since}",
    )


def position_signal(f: Facts) -> Signal:
    s, name = f.exporter_share, f.exporter_name
    if s < UNTAPPED:
        detail = (
            f"{name} doesn't sell here yet" if s == 0 else f"{name} holds under 1% of this market"
        )
        return Signal(kind="position", tone="positive", title=f"Untapped for {name}", detail=detail)
    if s < ESTABLISHED:
        return Signal(
            kind="position",
            tone="positive",
            title="Room to grow",
            detail=f"{name} holds {percent(s)} of this market",
        )
    if s < LEADING:
        return Signal(
            kind="position",
            tone="neutral",
            title=f"{name} is established",
            detail=f"{name} already holds {percent(s)} of this market",
        )
    return Signal(
        kind="position",
        tone="neutral",
        title=f"{name} leads here",
        detail=f"{name} already holds {percent(s)} of this market",
    )


def size_signal(f: Facts) -> Signal:
    v, year = f.market_imports_usd, f.end_year
    title = (
        "Very large market"
        if v >= VERY_LARGE
        else "Large market"
        if v >= LARGE
        else "Mid-size market"
        if v >= MID_SIZE
        else "Niche market"
    )
    return Signal(
        kind="size", tone="neutral", title=title, detail=f"{money(v)} of imports in {year}"
    )


def signals(f: Facts) -> list[Signal]:
    return [demand_signal(f), competition_signal(f), position_signal(f), size_signal(f)]


# ---------- verdict ----------
def verdict(f: Facts) -> Verdict:
    """One recommended action. Rules are checked in order; the first that applies wins."""
    demand, competition, position, size = signals(f)
    rival = f.rival_name or "the main supplier"

    def build(
        action: Action, headline: str, tone: Tone, evidence: list[Signal], step: str
    ) -> Verdict:
        summary = ". ".join(s.detail for s in evidence) + "."
        return Verdict(action=action, headline=headline, tone=tone, summary=summary, next_step=step)

    if f.exporter_share >= ESTABLISHED:
        if f.import_growth_3y <= SHRINKING:
            return build(
                "defend",
                "Defend your position",
                "neutral",
                [position, demand],
                "Protect your share in a shrinking market: keep key buyers and watch prices.",
            )
        if (f.top_rival_share_change or 0.0) >= RIVAL_GAINING:
            return build(
                "defend",
                "Defend your position",
                "neutral",
                [position, competition],
                f"Watch prices and delivery against {rival}, who is gaining share.",
            )
        return build(
            "grow",
            "Grow your lead",
            "positive",
            [position, demand],
            "Build on it: widen your range and distribution in this market.",
        )
    if f.import_growth_3y <= SHRINKING:
        return build(
            "care",
            "Approach with care",
            "negative",
            [demand, size],
            "Only pursue it with a clear edge on price or quality.",
        )
    if _dominated(f):
        return build(
            "hard",
            "Hard to break in",
            "negative",
            [competition, position],
            f"Look for buyers who want an alternative to {rival}, or a niche it ignores.",
        )
    if f.import_growth_3y >= GROWTH:
        evidence = [demand, position] + ([competition] if competition.tone == "positive" else [])
        return build(
            "go",
            "Go for it",
            "positive",
            evidence,
            "Shortlist it: check tariffs and certifications, then contact importers.",
        )
    return build(
        "test",
        "Worth testing",
        "neutral",
        [size, demand],
        "Test with a small shipment or a trade fair before committing.",
    )


# ---------- reasons (the original three lines) ----------
def _growth(f: Facts) -> str:
    years = f"from {f.start_year} to {f.end_year}"
    if f.import_growth_3y >= STEADY_WITHIN:
        return f"Imports grew {percent(f.import_growth_3y)} a year {years}"
    if f.import_growth_3y <= -STEADY_WITHIN:
        return f"Imports fell {percent(-f.import_growth_3y)} a year {years}"
    return f"Imports held steady {years}"


def _competition(f: Facts) -> str:
    change = f.top_rival_share_change
    if f.rival_name is None or change is None:
        return f"A {money(f.market_imports_usd)} market in {f.end_year}"
    if change <= -STEADY_WITHIN:
        return f"{f.rival_name}'s share fell {_points(change)} since {f.start_year}"
    if change >= STEADY_WITHIN:
        return f"{f.rival_name} gained {_points(change)} of share since {f.start_year}"
    return f"{f.rival_name}'s share held steady since {f.start_year}"


def _room(f: Facts) -> str:
    if f.exporter_share < 0.01:
        return f"{f.exporter_name} holds under 1% of this market: room to grow"
    if f.exporter_share < ESTABLISHED:
        return f"{f.exporter_name} holds {percent(f.exporter_share)} of this market: room to grow"
    return f"{f.exporter_name} already holds {percent(f.exporter_share)} of this market"


def reasons(facts: Facts) -> list[str]:
    """Demand, competition, room to grow: one line each."""
    return [_growth(facts), _competition(facts), _room(facts)]
