"""Quotes and proforma invoices, priced by Incoterms® 2020 rules.

  FOB  goods loaded on board at the origin port. The seller's costs up to then (inland
       transport, export clearance, terminal handling) are inside the FOB price.
  CFR  FOB + sea freight to the destination port.
  CIF  CFR + cargo insurance (the usual cover: 110% of goods and freight, at 0.3%).
  DAP  CIF + unloading/handling at the destination (and inland transport for landlocked
       markets). Import duty and taxes stay with the buyer.

Freight comes from our estimate (the typical figure) unless the seller enters their
forwarder's figure. An issued quote stores a full snapshot and a number taken from an
atomic per-user counter.
"""

from __future__ import annotations

import logging
import math
import uuid
from datetime import UTC, date, datetime, timedelta

import httpx
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.core.config import Settings
from whitespace_api.models.pipeline import PipelineContact
from whitespace_api.models.profile import UserProfile
from whitespace_api.models.quotes import BusinessDetails, Quote
from whitespace_api.models.user import User
from whitespace_api.repositories import trade as trade_repo
from whitespace_api.schemas.freight import FreightEstimate
from whitespace_api.schemas.quotes import (
    BusinessIn,
    BusinessOut,
    Party,
    Payment,
    PaymentTerms,
    QuoteIn,
    QuoteLine,
    QuoteOut,
    QuoteSummary,
)
from whitespace_api.services import freight as freight_service
from whitespace_api.services import landed_cost
from whitespace_shared.naming import everyday_name

log = logging.getLogger(__name__)

INSURANCE_RATE = 0.003
INSURED_SHARE = 1.10

PAYMENTS: dict[PaymentTerms, Payment] = {
    "advance": Payment(
        key="advance", label="100% in advance",
        text="100% payment by bank transfer (T/T) before shipment.",
        risk="low",
        explain="Safest for you; buyers often refuse it for a first order.",
    ),
    "deposit_30": Payment(
        key="deposit_30", label="30% deposit, 70% against documents",
        text="30% deposit by T/T with the order; 70% balance by T/T against a copy of the "
        "bill of lading.",
        risk="medium",
        explain="The usual first-order compromise: the deposit covers your costs if the "
        "buyer walks away, and you hold the original bill of lading until the balance is paid.",
    ),
    "lc_sight": Payment(
        key="lc_sight", label="Letter of credit at sight",
        text="Irrevocable letter of credit at sight, issued by a first-class bank.",
        risk="low",
        explain="The buyer's bank promises to pay once your documents match the credit "
        "exactly. Safe, but bank fees apply and document errors delay payment.",
    ),
    "cad": Payment(
        key="cad", label="Cash against documents",
        text="Cash against documents (D/P at sight) through the buyer's bank.",
        risk="medium",
        explain="The buyer gets the shipping documents only when they pay, but can refuse "
        "the goods, leaving them at the destination port.",
    ),
    "open_30": Payment(
        key="open_30", label="Open account, 30 days",
        text="Payment by T/T within 30 days of the bill of lading date.",
        risk="high",
        explain="You ship first and trust the buyer to pay: only for buyers you know well, "
        "or with export credit insurance.",
    ),
}  # fmt: skip


class QuoteError(Exception):
    """Can't price this quote. The message is safe to show."""


class NotFoundError(Exception):
    pass


def _r(value: float) -> float:
    return round(value + 1e-9, 2)


def _business_out(row: BusinessDetails | None) -> BusinessOut:
    fields = BusinessIn.model_fields
    values = {k: getattr(row, k) for k in fields} if row else {}
    out = BusinessOut(**values, complete=False)
    out.complete = bool(out.company_name and out.address)
    return out


async def get_business(db: AsyncSession, user: User) -> BusinessOut:
    return _business_out(await db.get(BusinessDetails, user.id))


async def save_business(db: AsyncSession, user: User, body: BusinessIn) -> BusinessOut:
    values = {k: (v.strip() or None) if isinstance(v, str) else v for k, v in body}
    await db.execute(
        insert(BusinessDetails)
        .values(user_id=user.id, **values)
        .on_conflict_do_update(
            index_elements=[BusinessDetails.user_id],
            set_={**values, "updated_at": datetime.now(UTC)},
        )
    )
    await db.commit()
    return await get_business(db, user)


def _sea(estimate: FreightEstimate) -> float:
    return sum(line.usd.typical for line in estimate.lines if line.key == "sea")


def _arrival(estimate: FreightEstimate) -> float:
    return sum(line.usd.typical for line in estimate.lines if line.stage == "after_arrival")


def _before_fob(estimate: FreightEstimate) -> float:
    return sum(
        line.usd.typical for line in estimate.lines if line.key in ("origin_fees", "origin_road")
    )


async def price(
    db: AsyncSession, http: httpx.AsyncClient, user: User, body: QuoteIn, settings: Settings
) -> QuoteOut:
    """The quote as it would be issued (no number yet, nothing saved)."""
    exporter = body.exporter or await db.scalar(
        select(UserProfile.exporter).where(UserProfile.user_id == user.id)
    )
    if not exporter:
        raise QuoteError("Set the country you export from in your profile first.")
    if exporter == body.market:
        raise QuoteError("The buyer's market is your own country.")
    product = await trade_repo.get_product(db, body.hs6)
    if product is None:
        raise NotFoundError(f"Unknown product {body.hs6}")
    countries = await trade_repo.countries_by_code(db, [exporter, body.market])
    if body.market not in countries or exporter not in countries:
        raise NotFoundError("Unknown country")
    if body.contact_id is not None:
        owned = await db.scalar(
            select(PipelineContact.id).where(
                PipelineContact.id == body.contact_id, PipelineContact.user_id == user.id
            )
        )
        if owned is None:
            raise NotFoundError("That company isn't in your pipeline")
    market_name, exporter_name = countries[body.market].name, countries[exporter].name

    # Freight: the container count comes from the estimate's load per box.
    shared = body.container == "lcl"
    try:
        estimate = await freight_service.estimate(
            db, http, origin=exporter, dest=body.market, hs6=body.hs6,
            container=body.container, kg=body.quantity_kg if shared else None,
            value_usd_kg=body.unit_price_fob,
        )  # fmt: skip
    except freight_service.NoRouteError:
        estimate = None
    if estimate is None and body.incoterm != "FOB" and body.freight_usd is None:
        raise QuoteError(
            f"We don't have a shipping route to {market_name} yet: quote FOB, or enter "
            "your forwarder's freight figure."
        )
    origin_port = estimate.route.origin_port if estimate else f"port of loading, {exporter_name}"
    dest_port = estimate.route.dest_port if estimate else f"port of discharge, {market_name}"
    per_box = estimate.kg_per_container if estimate and not shared else None
    containers = 1 if shared or not per_box else max(1, math.ceil(body.quantity_kg / per_box))

    goods = _r(body.quantity_kg * body.unit_price_fob)
    description = (body.description or "").strip() or everyday_name(
        body.hs6, product.description
    ).capitalize()
    lines = [
        QuoteLine(
            label=description,
            detail=f"HS {body.hs6} · {body.quantity_kg:,.0f} kg x "
            f"US${body.unit_price_fob:,.2f}/kg FOB {origin_port}",
            amount_usd=goods,
        )
    ]
    freight_basis = "none"
    sea = 0.0
    if body.incoterm != "FOB":
        if body.freight_usd is not None:
            sea, freight_basis = _r(body.freight_usd), "your figure"
        else:
            assert estimate is not None
            sea, freight_basis = _r(_sea(estimate) * containers), "estimate"
        what = "shared container (LCL)" if shared else f"{containers} x {body.container}"
        lines.append(QuoteLine(label=f"Sea freight to {dest_port}", detail=what, amount_usd=sea))
    if body.incoterm in ("CIF", "DAP"):
        insured = _r((goods + sea) * INSURED_SHARE)
        lines.append(
            QuoteLine(
                label="Cargo insurance",
                detail=f"{INSURANCE_RATE:.1%} of US${insured:,.0f} (110% of goods and freight)",
                amount_usd=_r(insured * INSURANCE_RATE),
            )
        )
    if body.incoterm == "DAP":
        if estimate is None:
            raise QuoteError("DAP needs our route estimate; quote CIF instead.")
        lines.append(
            QuoteLine(
                label=f"Unloading and handling at {dest_port}",
                detail="Destination terminal handling and delivery order",
                amount_usd=_r(_arrival(estimate) * containers),
            )
        )
    total = _r(sum(line.amount_usd for line in lines))
    named_place = origin_port if body.incoterm == "FOB" else dest_port
    issued = datetime.now(UTC).date()
    valid_until = issued + timedelta(days=body.validity_days)
    payment = PAYMENTS[body.payment_terms]

    terms = [
        f"Prices in US dollars, {body.incoterm} {named_place} (Incoterms® 2020).",
        f"Import duties, taxes and customs clearance in {market_name} are for the buyer's account.",
    ]
    if body.incoterm != "FOB":
        terms.append(
            "Freight is quoted at current rates and may be revised if carrier rates change "
            "before booking."
        )
    terms += [f"Payment: {payment.text}", f"Valid until {valid_until:%d %B %Y}."]

    seller_notes: list[str] = []
    if freight_basis == "estimate":
        seller_notes.append(
            "Sea freight is our typical estimate. Get a forwarder's quote and enter it "
            "before sending, as rates move week to week."
        )
    if estimate:
        seller_notes.append(
            f"Your FOB price must already cover getting the goods loaded at {origin_port}: "
            f"about US${_before_fob(estimate) * containers:,.0f} in port handling, export "
            "papers" + (" and inland transport" if estimate.route.origin_inland_km else "") + "."
        )
    if per_box and not shared:
        last = (body.quantity_kg - per_box * (containers - 1)) / per_box
        if last < 0.6:
            seller_notes.append(
                f"The {'last ' if containers > 1 else ''}container is only about {last:.0%} "
                "full: consider a smaller box, a shared container, or a bigger order."
            )
    try:
        duty = await landed_cost.duties(
            db, http, exporter=exporter, market=body.market, hs6=body.hs6, settings=settings
        )
        rate = duty.yours
        scheme = f" under {rate.scheme}" if rate.scheme else ""
        seller_notes.append(
            f"The buyer pays {landed_cost.rate_text(rate.rate_pct)} import duty{scheme} on "
            f"this product from {exporter_name}"
            + (": worth mentioning, it's a selling point." if rate.rate_pct == 0 else ".")
        )
    except Exception as exc:  # the quote doesn't need it
        log.info("No duty note for quote: %s", type(exc).__name__)

    business = await db.get(BusinessDetails, user.id)
    seller = Party(
        name=(business.company_name if business and business.company_name else user.full_name),
        address=business.address if business else None,
        country=exporter_name,
        phone=business.phone if business else None,
        email=(business.email if business and business.email else user.email),
        website=business.website if business else None,
        tax_id=business.tax_id if business else None,
    )
    if not (business and business.company_name and business.address):
        seller_notes.append("Add your company name and address in Settings → Business.")
    return QuoteOut(
        id=None,
        number=None,
        kind=body.kind,
        issued=issued,
        valid_until=valid_until,
        seller=seller,
        buyer=Party(
            name=body.buyer_name.strip(),
            address=(body.buyer_address or "").strip() or None,
            country=market_name,
        ),
        bank_details=business.bank_details if business else None,
        hs6=body.hs6,
        description=description,
        market=body.market,
        incoterm=body.incoterm,
        named_place=named_place,
        origin_port=origin_port,
        dest_port=dest_port,
        quantity_kg=body.quantity_kg,
        containers=containers,
        container=body.container,
        unit_price_fob=body.unit_price_fob,
        lines=lines,
        total_usd=total,
        unit_price_usd_kg=round(total / body.quantity_kg, 4),
        payment=payment,
        terms=terms,
        freight_basis=freight_basis,
        seller_notes=seller_notes,
        contact_id=body.contact_id,
        created_at=None,
    )


async def _next_number(db: AsyncSession, user: User, year: int) -> str:
    """Atomic: the row lock on UPDATE serialises concurrent quotes for one user."""
    await db.execute(insert(BusinessDetails).values(user_id=user.id).on_conflict_do_nothing())
    n = await db.scalar(
        update(BusinessDetails)
        .where(BusinessDetails.user_id == user.id)
        .values(next_quote=BusinessDetails.next_quote + 1)
        .returning(BusinessDetails.next_quote - 1)
    )
    return f"Q-{year}-{int(n or 0):04d}"


async def create(
    db: AsyncSession, http: httpx.AsyncClient, user: User, body: QuoteIn, settings: Settings
) -> QuoteOut:
    out = await price(db, http, user, body, settings)
    number = await _next_number(db, user, out.issued.year)
    if out.kind == "proforma":
        number = number.replace("Q-", "PI-", 1)
    quote_id = uuid.uuid4()
    now = datetime.now(UTC)
    out = out.model_copy(update={"id": quote_id, "number": number, "created_at": now})
    db.add(
        Quote(
            id=quote_id,
            user_id=user.id,
            number=number,
            kind=out.kind,
            hs6=out.hs6,
            market=out.market,
            buyer_name=out.buyer.name,
            contact_id=out.contact_id,
            total_usd=out.total_usd,
            content=out.model_dump(mode="json"),
            created_at=now,
        )
    )
    await db.commit()
    return out


async def list_quotes(db: AsyncSession, user: User) -> list[QuoteSummary]:
    rows = await db.scalars(
        select(Quote).where(Quote.user_id == user.id).order_by(Quote.created_at.desc()).limit(200)
    )
    return [
        QuoteSummary(
            id=q.id,
            number=q.number,
            kind=q.kind,
            buyer_name=q.buyer_name,
            market=q.market,
            hs6=q.hs6,
            total_usd=float(q.total_usd),
            created_at=q.created_at,
        )
        for q in rows
    ]


async def get(db: AsyncSession, user: User, quote_id: uuid.UUID) -> QuoteOut:
    row = await db.scalar(select(Quote).where(Quote.id == quote_id, Quote.user_id == user.id))
    if row is None:
        raise NotFoundError("Quote not found")
    return QuoteOut.model_validate(row.content)


async def remove(db: AsyncSession, user: User, quote_id: uuid.UUID) -> None:
    result = await db.execute(
        delete(Quote).where(Quote.id == quote_id, Quote.user_id == user.id).returning(Quote.id)
    )
    await db.commit()
    if result.first() is None:
        raise NotFoundError("Quote not found")


def today() -> date:
    return datetime.now(UTC).date()
