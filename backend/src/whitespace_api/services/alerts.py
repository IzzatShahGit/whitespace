"""Alerts: turn fresh monthly customs data into notifications for the people watching.

Each watched (market, product) is read through the shared monthly cache (refreshed when
old) and measured for each watcher's country: imports in the latest 3 months against
the same months a year earlier (so seasons cancel out), the country's share of the last
12 months against the 12 before, and the same for its largest rival.

Only meaningful moves become notifications: a quiet month sends nothing, so a bell that
rings is worth opening. Measuring and judging are pure functions, as in explain.py: the
same data always gives the same words, every sentence states its figures, and every
threshold is named here.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.core.config import Settings
from whitespace_api.integrations import monthly_trade as source
from whitespace_api.models.watch import Notification, Watch
from whitespace_api.notify.email import EmailMessage, Sender
from whitespace_api.repositories import monthly as monthly_repo
from whitespace_api.repositories import notifications as notification_repo
from whitespace_api.repositories import trade as trade_repo
from whitespace_api.repositories import watches as watch_repo
from whitespace_api.schemas.trade import RecentMovement, RecentSupplier, Tone
from whitespace_api.schemas.watch import NotificationKind
from whitespace_api.services import recent as recent_service
from whitespace_api.services.explain import EN_DASH, money, percent
from whitespace_shared.naming import everyday_name

log = logging.getLogger(__name__)

# ---------- thresholds ----------
# Imports: the latest 3 months vs the same 3 months a year earlier.
QUARTER = 3
IMPORTS_ROSE = 0.20
IMPORTS_FELL = -0.20
# The watcher's country: its share of the last 12 months vs the 12 before (0.02 = 2 points).
SHARE_ROSE = 0.02
SHARE_FELL = -0.02
# The largest supplier other than the watcher's country, same windows.
RIVAL_SLIPPED = -0.03
# Markets importing less than this in 12 months (EUR or USD, as the source reports) never
# alert: there, a single shipment more or less swings every percentage.
MIN_IMPORTS_12M = 200_000
# Sources publish about two months after a month ends. A latest month older than this
# means the trade has stopped, which is no news to announce.
FRESH_WITHIN_MONTHS = 6

YEAR = 12  # months
CURRENCY_SYMBOLS = {"EUR": "€", "USD": "$"}
MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def monthly_markets(settings: Settings) -> frozenset[str]:
    """Markets alerts can cover: EU members, and the US when a Census key is set (US
    monthly data can't be fetched without one)."""
    if settings.census_api_key is None:
        return frozenset(source.EU_MEMBERS)
    return source.COVERED_MARKETS


# ---------- months and words ----------
def _index(month: str) -> int:
    """Months since year 0 for a YYYY-MM month, so months can be added and subtracted."""
    year, number = month.split("-")
    return int(year) * 12 + int(number) - 1


def shift(month: str, months: int) -> str:
    index = _index(month) + months
    return f"{index // 12}-{index % 12 + 1:02d}"


def month_name(month: str) -> str:
    """In words: 2026-08 is Aug 2026."""
    return f"{MONTH_NAMES[_index(month) % 12]} {month[:4]}"


def period(first: str, last: str) -> str:
    """In words, with an en dash: Jun to Aug 2026, or Nov 2025 to Jan 2026 across years."""
    start = MONTH_NAMES[_index(first) % 12] if first[:4] == last[:4] else month_name(first)
    return f"{start}{EN_DASH}{month_name(last)}"


def is_fresh(latest_month: str, today: date) -> bool:
    return _index(f"{today:%Y-%m}") - _index(latest_month) <= FRESH_WITHIN_MONTHS


def _money(value: float, currency: str) -> str:
    """explain.money's rounding in the source's currency: €31M, $4.2M."""
    return money(value).replace("$", CURRENCY_SYMBOLS.get(currency, f"{currency} "), 1)


def _pct(share: float) -> str:
    """A share, with one decimal below 10%, where whole numbers hide moves (0.4% -> 2.4%)."""
    return f"{share * 100:.1f}%" if share < 0.10 else percent(share)


def _possessive(name: str) -> str:
    return f"{name}'" if name.endswith("s") else f"{name}'s"


# ---------- measuring ----------
@dataclass(frozen=True)
class Facts:
    """The latest monthly data, as seen by one watcher's country. Names are for sentences."""

    exporter: str  # the watcher's country, e.g. "Pakistan"
    product: str  # everyday name, e.g. "towels"
    market: str  # e.g. "Germany"
    currency: str
    latest_month: str  # YYYY-MM
    imports_12m: float
    quarter: float | None  # imports in the latest 3 months; None if a month is missing
    quarter_year_ago: float | None  # the same 3 months a year earlier
    share: float  # the watcher's country, last 12 months
    share_before: float | None  # the 12 months before; None with under two years of data
    rival: RecentSupplier | None  # the largest supplier other than the watcher's country


def rivals_of(
    movement: RecentMovement, payload: dict[str, Any], exporter: str
) -> list[RecentSupplier]:
    """The largest suppliers other than the watcher's country, largest first.

    Sources name suppliers their own way, so the watcher's country is recognised by the
    name the source gives its code. A country the source has no code for can't be told
    apart from its rivals: then there are none to report.
    """
    code = source.EXPORTER_CODES.get(exporter, {}).get(payload["source"])
    if code is None:
        return []
    own = payload["partners"].get(code, {}).get("name")
    return [s for s in movement.suppliers if s.name != own]


def measure(
    movement: RecentMovement,
    rivals: Sequence[RecentSupplier],
    *,
    exporter: str,
    product: str,
    market: str,
) -> Facts:
    totals = {p.month: p.total for p in movement.months}  # only months with imports
    latest = movement.latest_month
    quarter = [shift(latest, -back) for back in reversed(range(QUARTER))]
    year_ago = [shift(month, -YEAR) for month in quarter]
    complete = all(month in totals for month in quarter + year_ago)  # like with like
    return Facts(
        exporter=exporter,
        product=product,
        market=market,
        currency=movement.currency,
        latest_month=latest,
        imports_12m=sum(p.total for p in movement.months[-recent_service.WINDOW :]),
        quarter=sum(totals[m] for m in quarter) if complete else None,
        quarter_year_ago=sum(totals[m] for m in year_ago) if complete else None,
        share=movement.exporter_share_recent,
        share_before=movement.exporter_share_before,
        rival=rivals[0] if rivals else None,
    )


# ---------- judging ----------
@dataclass(frozen=True)
class Alert:
    kind: NotificationKind
    tone: Tone
    month: str  # the latest month of data it reports on, YYYY-MM
    title: str
    body: str
    figures: dict[str, Any]


def alerts(f: Facts, *, today: date) -> list[Alert]:
    """The meaningful moves in `f`; none when its data is old or the market is tiny."""
    if not is_fresh(f.latest_month, today) or f.imports_12m < MIN_IMPORTS_12M:
        return []
    found = (_imports_moved(f), _share_moved(f), _rival_slipped(f))
    return [alert for alert in found if alert is not None]


def _topic(f: Facts) -> str:
    """The start of every title, e.g. "Towels in Germany"."""
    return f"{f.product[:1].upper()}{f.product[1:]} in {f.market}"


def _imports_moved(f: Facts) -> Alert | None:
    if f.quarter is None or f.quarter_year_ago is None:
        return None
    change = f.quarter / f.quarter_year_ago - 1
    if IMPORTS_FELL < change < IMPORTS_ROSE:
        return None
    rose = change > 0
    moved = percent(abs(change))
    first = shift(f.latest_month, 1 - QUARTER)
    year_ago = period(shift(first, -YEAR), shift(f.latest_month, -YEAR))
    advice = (
        "Demand is growing: a good time to follow up with buyers there."
        if rose
        else "Demand is cooling: check orders and prices with buyers before shipping more."
    )
    return Alert(
        kind="imports_up" if rose else "imports_down",
        tone="positive" if rose else "negative",
        month=f.latest_month,
        title=f"{_topic(f)}: imports {'up' if rose else 'down'} {moved}",
        body=(
            f"{f.market} imported {_money(f.quarter, f.currency)} of {f.product} in "
            f"{period(first, f.latest_month)}, {moved} {'more' if rose else 'less'} than a "
            f"year earlier ({_money(f.quarter_year_ago, f.currency)} in {year_ago}). {advice}"
        ),
        figures={
            "change": change,
            "imports": f.quarter,
            "imports_year_ago": f.quarter_year_ago,
            "currency": f.currency,
            "months": [first, f.latest_month],
        },
    )


def _share_moved(f: Facts) -> Alert | None:
    if f.share_before is None:
        return None
    change = f.share - f.share_before
    if SHARE_FELL < change < SHARE_ROSE:
        return None
    rose = change > 0
    direction = "up" if rose else "down"
    advice = (
        f"{f.exporter} is gaining ground with buyers there."
        if rose
        else "Other suppliers are winning orders there: worth checking how your prices "
        "and delivery compare."
    )
    return Alert(
        kind="share_up" if rose else "share_down",
        tone="positive" if rose else "negative",
        month=f.latest_month,
        title=f"{_topic(f)}: {_possessive(f.exporter)} share {direction} to {_pct(f.share)}",
        body=(
            f"{f.exporter} supplied {_pct(f.share)} of {_possessive(f.market)} imports of "
            f"{f.product} in the 12 months to {month_name(f.latest_month)}, {direction} from "
            f"{_pct(f.share_before)} in the 12 months before. {advice}"
        ),
        figures={"share": f.share, "share_before": f.share_before},
    )


def _rival_slipped(f: Facts) -> Alert | None:
    rival = f.rival
    if rival is None or rival.share_before is None:
        return None
    if rival.share_recent - rival.share_before > RIVAL_SLIPPED:
        return None
    return Alert(
        kind="rival_slipping",
        tone="positive",
        month=f.latest_month,
        title=f"{_topic(f)}: {rival.name} is losing ground",
        body=(
            f"{rival.name}, the largest supplier besides {f.exporter}, had "
            f"{_pct(rival.share_recent)} of {_possessive(f.market)} imports of {f.product} in "
            f"the 12 months to {month_name(f.latest_month)}, down from "
            f"{_pct(rival.share_before)} in the 12 months before. Some of its buyers may be "
            "looking for other suppliers: a chance to win them."
        ),
        figures={
            "rival": rival.name,
            "share": rival.share_recent,
            "share_before": rival.share_before,
        },
    )


# ---------- notifying ----------
def notification_row(watch: Watch, alert: Alert) -> dict[str, Any]:
    """One watcher's notification. The dedupe key names the fact (kind, pair, data
    month), so each fact is announced once, however often the job runs."""
    pair = {"exporter": watch.exporter, "hs6": watch.hs6, "market": watch.market}
    return {
        "user_id": watch.user_id,
        "kind": alert.kind,
        "title": alert.title,
        "body": alert.body,
        "link": f"/app/markets/{watch.hs6}/{watch.market}?exporter={watch.exporter}",
        "data": {**pair, "month": alert.month, "tone": alert.tone, **alert.figures},
        "dedupe_key": ":".join((alert.kind, *pair.values(), alert.month)),
    }


async def check_pair(
    db: AsyncSession,
    *,
    market: str,
    hs6: str,
    settings: Settings,
    today: date,
    sender: Sender | None = None,
) -> int:
    """Notify everyone watching this pair of meaningful moves in its latest data.

    Returns how many notifications are new. Raises recent_service.UnavailableError when
    the source can't be reached and nothing is saved. With a `sender`, new notifications
    are also emailed.
    """
    watches = await watch_repo.watching(db, market=market, hs6=hs6)
    if not watches:
        return 0
    exporters = sorted({w.exporter for w in watches})
    found = await _alerts_by_exporter(
        db, market=market, hs6=hs6, exporters=exporters, settings=settings, today=today
    )
    rows = [notification_row(w, alert) for w in watches for alert in found[w.exporter]]
    created = await notification_repo.add_many(db, rows)
    await db.commit()
    if sender is not None and created:
        await _email(db, created, sender, settings.public_app_url)
    return len(created)


async def _alerts_by_exporter(
    db: AsyncSession,
    *,
    market: str,
    hs6: str,
    exporters: list[str],
    settings: Settings,
    today: date,
) -> dict[str, list[Alert]]:
    product, names = await _names(db, hs6=hs6, codes=[market, *exporters])
    found: dict[str, list[Alert]] = {}
    for exporter in exporters:
        # The shared service refreshes the saved copy when it's old, and keeps serving
        # it (marked stale) when the source is down.
        movement = await recent_service.recent_movement(
            db, market=market, hs6=hs6, exporter=exporter, settings=settings
        )
        saved = await monthly_repo.get_cached(db, market, hs6)  # the copy it just used
        facts = measure(
            movement,
            rivals_of(movement, saved.payload, exporter) if saved else [],
            exporter=names[exporter],
            product=product,
            market=names[market],
        )
        found[exporter] = alerts(facts, today=today)
    return found


async def _names(db: AsyncSession, *, hs6: str, codes: list[str]) -> tuple[str, dict[str, str]]:
    """The product's everyday name, and country names (codes if the data lacks them)."""
    product = await trade_repo.get_product(db, hs6)
    countries = await trade_repo.countries_by_code(db, codes)
    names = {code: countries[code].name if code in countries else code for code in codes}
    return (everyday_name(hs6, product.description) if product else f"product {hs6}"), names


async def _email(
    db: AsyncSession, notifications: Sequence[Notification], sender: Sender, app_url: str
) -> None:
    """One email per new notification. Best effort: a failed send is logged (never the
    address) and the in-app notification stands."""
    addresses = await notification_repo.recipients(db, {n.user_id for n in notifications})
    for n in notifications:
        to = addresses.get(n.user_id)
        if to is None:  # deactivated account
            continue
        message = EmailMessage(to=to, subject=n.title, text=f"{n.body}\n\n{app_url}{n.link or ''}")
        try:
            await sender.send(message)
        except Exception as exc:
            log.warning("Alert email for notification %s not sent: %s", n.id, type(exc).__name__)
