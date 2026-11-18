"""Shipping documents for a won deal, built from the quote the buyer accepted.

  commercial invoice  the quote's prices, a sequential invoice number, shipping details
  packing list        packages, net/gross weight, volume and marks
  proof of origin     for EU GSP lanes, the "statement on origin" in the wording of
                      Annex 22-07 to Commission Implementing Regulation (EU) 2015/2447;
                      elsewhere, where to get a certificate (we don't invent wordings)
  checklist           what's ready, what to fill in, what comes from others (the B/L,
                      insurance, export declaration) plus the lane's researched rules

Concurrency: creating locks the quote row, so a double click can't make two shipments or
skip an invoice number (invoices must be numbered without gaps). Edits lock the
shipment row and check the version the client saw.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, date, datetime

import httpx
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.core.config import Settings
from whitespace_api.integrations import fx
from whitespace_api.integrations.monthly_trade import EU_MEMBERS
from whitespace_api.models.profile import UserProfile
from whitespace_api.models.quotes import BusinessDetails, Quote
from whitespace_api.models.requirements import MarketRequirements, RequirementCheck
from whitespace_api.models.shipments import Shipment as ShipmentRow
from whitespace_api.models.user import User
from whitespace_api.schemas.quotes import QuoteOut
from whitespace_api.schemas.shipments import (
    ChecklistItem,
    OriginStatement,
    Shipment,
    ShipmentDetails,
    ShipmentPatch,
    ShipmentSummary,
)
from whitespace_api.services import landed_cost

log = logging.getLogger(__name__)
GSP_SELF_CERTIFY_EUR = 6_000  # without REX registration, only up to this value per shipment

EU_GSP_STATEMENT = (
    "The exporter {rex} of the products covered by this document declares that, except "
    "where otherwise clearly indicated, these products are of {country} preferential origin "
    "according to rules of origin of the Generalised System of Preferences of the European "
    "Union and that the origin criterion met is {criterion}."
)


class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    pass


def _today() -> date:
    return datetime.now(UTC).date()


async def _next_invoice(db: AsyncSession, user: User, year: int) -> str:
    await db.execute(insert(BusinessDetails).values(user_id=user.id).on_conflict_do_nothing())
    n = await db.scalar(
        update(BusinessDetails)
        .where(BusinessDetails.user_id == user.id)
        .values(next_invoice=BusinessDetails.next_invoice + 1)
        .returning(BusinessDetails.next_invoice - 1)
    )
    return f"INV-{year}-{int(n or 0):04d}"


async def _scheme(
    db: AsyncSession, http: httpx.AsyncClient, exporter: str, market: str, hs6: str, s: Settings
) -> str | None:
    try:
        duty = await landed_cost.duties(
            db, http, exporter=exporter, market=market, hs6=hs6, settings=s
        )
    except Exception as exc:  # documents work without it; origin guidance stays generic
        log.info("No duty data for shipment: %s", type(exc).__name__)
        return None
    return duty.yours.scheme if duty.yours.kind == "preference" else None


async def create(
    db: AsyncSession, http: httpx.AsyncClient, user: User, quote_id: uuid.UUID, settings: Settings
) -> tuple[Shipment, bool]:
    """(shipment, created). One per quote: asking again returns the existing one."""
    quote = await db.scalar(
        select(Quote).where(Quote.id == quote_id, Quote.user_id == user.id).with_for_update()
    )
    if quote is None:
        await db.rollback()
        raise NotFoundError("Quote not found")
    existing = await db.scalar(select(ShipmentRow).where(ShipmentRow.quote_id == quote_id))
    if existing is not None:
        await db.commit()
        return await render(db, http, user, existing), False
    snapshot = QuoteOut.model_validate(quote.content)
    exporter = snapshot.exporter or await db.scalar(
        select(UserProfile.exporter).where(UserProfile.user_id == user.id)
    )
    scheme = (
        await _scheme(db, http, exporter, snapshot.market, snapshot.hs6, settings)
        if exporter
        else None
    )
    today = _today()
    number = await _next_invoice(db, user, today.year)
    details = ShipmentDetails(
        invoice_date=today,
        consignee_address=snapshot.buyer.address,
        net_kg=snapshot.quantity_kg,
    )
    row = ShipmentRow(
        id=uuid.uuid4(),
        user_id=user.id,
        quote_id=quote.id,
        invoice_number=number,
        hs6=snapshot.hs6,
        market=snapshot.market,
        buyer_name=snapshot.buyer.name,
        content={
            "quote": quote.content,
            "quote_number": quote.number,
            "exporter": exporter,
            "scheme": scheme,
            "details": details.model_dump(mode="json"),
        },
    )
    db.add(row)
    await db.commit()
    return await render(db, http, user, row), True


def volume_m3(details: ShipmentDetails) -> float | None:
    if not details.package_size_cm or not details.packages:
        return None
    sizes = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", details.package_size_cm)]
    if len(sizes) != 3:
        return None
    return round(sizes[0] * sizes[1] * sizes[2] / 1_000_000 * details.packages, 2)


async def _eur_per_usd(http: httpx.AsyncClient) -> float | None:
    try:
        return (await fx.rates(http)).per_usd.get("EUR")
    except Exception:  # the check is advisory
        return None


async def render(
    db: AsyncSession, http: httpx.AsyncClient, user: User, row: ShipmentRow
) -> Shipment:
    q = QuoteOut.model_validate(row.content["quote"])
    d = ShipmentDetails.model_validate(row.content.get("details") or {})
    scheme: str | None = row.content.get("scheme")
    business = await db.get(BusinessDetails, user.id)
    rex = business.rex_number if business else None
    origin_country = q.seller.country
    goods_usd = q.lines[0].amount_usd if q.lines else q.total_usd
    warnings: list[str] = []

    # --- proof of origin ---
    eu_gsp = bool(scheme and scheme.upper().startswith("EU GSP") and q.market in EU_MEMBERS)
    if eu_gsp:
        heading = f"{q.hs6[:2]}{q.hs6[2:4]}"
        text = EU_GSP_STATEMENT.format(
            rex=rex or "…", country=origin_country, criterion=d.origin_criterion or "…"
        )
        guidance = [
            "Print this statement on the commercial invoice (or another commercial document "
            "describing the goods), then sign and date it.",
            f"Origin criterion: “P” if the goods are wholly obtained in {origin_country}; "
            f"otherwise “W” followed by the HS heading, e.g. “W {heading[:2]}.{heading[2:]}”, "
            "when they meet the product-specific rule of the GSP rules of origin.",
            f"Check the product-specific rule for heading {heading[:2]}.{heading[2:]} before "
            "you sign: some products must go through more than one process in "
            f"{origin_country}.",
        ]
        eur = await _eur_per_usd(http)
        if not rex:
            limit = f"€{GSP_SELF_CERTIFY_EUR:,}" + (
                f" (about US${GSP_SELF_CERTIFY_EUR / eur:,.0f})" if eur else ""
            )
            guidance.insert(
                1,
                "Exporters registered in the REX system put their REX number here. Without "
                f"one, you may only make this statement when the originating goods in the "
                f"shipment are worth {limit} or less.",
            )
            if eur and goods_usd * eur > GSP_SELF_CERTIFY_EUR:
                warnings.append(
                    f"The goods are worth about €{goods_usd * eur:,.0f}: above €6,000 the "
                    "origin statement needs your REX number (Settings → Business). Without "
                    "it the buyer may have to pay the full duty."
                )
        if not d.origin_criterion:
            warnings.append("Fill in the origin criterion for the statement on origin.")
        origin = OriginStatement(kind="eu_gsp_statement", text=text, guidance=guidance)
    else:
        origin = OriginStatement(
            kind="certificate",
            text=None,
            guidance=[
                "A certificate of origin is usually issued by your chamber of commerce or "
                "export promotion authority: apply with this commercial invoice and packing "
                "list.",
                "If a trade agreement lowers the duty in this market, it has its own origin "
                "form: ask the issuing authority which one applies.",
            ],
        )

    # --- checklist ---
    packing_ready = bool(d.packages and d.gross_kg and d.net_kg)
    checklist = [
        ChecklistItem(
            title="Commercial invoice", status="ready",
            detail=f"{row.invoice_number}, from quote {row.content.get('quote_number') or '-'}",
        ),
        ChecklistItem(
            title="Packing list", status="ready" if packing_ready else "fill_in",
            detail="Ready to print." if packing_ready
            else "Add the number of packages and the gross weight.",
        ),
        ChecklistItem(
            title="Statement on origin" if eu_gsp else "Certificate of origin",
            status=("ready" if rex and d.origin_criterion else "fill_in")
            if eu_gsp else "from_others",
            detail="Printed on the commercial invoice." if eu_gsp
            else "From your chamber of commerce or export authority.",
        ),
        ChecklistItem(
            title="Bill of lading", status="ready" if d.bl_number else "from_others",
            detail=f"No. {d.bl_number}" if d.bl_number
            else "Issued by the shipping line or your forwarder once the goods are loaded.",
        ),
        ChecklistItem(
            title="Export declaration", status="from_others",
            detail=f"Filed with {origin_country} customs by your customs agent before loading.",
        ),
    ]  # fmt: skip
    if q.incoterm in ("CIF", "DAP"):
        checklist.append(
            ChecklistItem(
                title="Insurance certificate",
                status="from_others",
                detail="From your cargo insurer, covering at least 110% of the CIF value "
                f"(about US${(q.total_usd) * 1.1:,.0f}).",
            )
        )
    exporter = row.content.get("exporter")
    if exporter:
        researched = await db.get(MarketRequirements, (row.hs6, row.market, exporter))
        items = (researched.content or {}).get("items", []) if researched else []
        papers = [i for i in items if i.get("category") in ("document", "certificate")]
        if papers:
            ticked = set(
                await db.scalars(
                    select(RequirementCheck.item).where(
                        RequirementCheck.user_id == user.id,
                        RequirementCheck.hs6 == row.hs6,
                        RequirementCheck.market == row.market,
                    )
                )
            )
            for item in papers[:8]:
                checklist.append(
                    ChecklistItem(
                        title=item["title"],
                        status="ready" if item["key"] in ticked else "from_others",
                        detail=item.get("detail", ""),
                    )
                )

    # --- consistency ---
    if not q.buyer.address and not d.consignee_address:
        warnings.append("Add the buyer's address: customs need it on the invoice.")
    if not (business and business.company_name and business.address):
        warnings.append("Add your company name and address in Settings → Business.")
    if d.net_kg and abs(d.net_kg - q.quantity_kg) > 0.005 * q.quantity_kg:
        warnings.append(
            f"The net weight ({d.net_kg:,.0f} kg) differs from the invoiced quantity "
            f"({q.quantity_kg:,.0f} kg): the invoice and packing list must agree."
        )
    if d.net_kg and d.gross_kg and d.gross_kg < d.net_kg:
        warnings.append("The gross weight is less than the net weight.")

    return Shipment(
        id=row.id,
        version=row.version,
        quote_id=row.quote_id,
        quote_number=row.content.get("quote_number"),
        invoice_number=row.invoice_number,
        hs6=q.hs6,
        market=q.market,
        description=q.description,
        seller=q.seller.model_copy(
            update={
                "name": business.company_name or q.seller.name,
                "address": business.address or q.seller.address,
                "phone": business.phone or q.seller.phone,
                "tax_id": business.tax_id or q.seller.tax_id,
            }
        )
        if business
        else q.seller,
        buyer=q.buyer.model_copy(update={"address": d.consignee_address or q.buyer.address}),
        bank_details=business.bank_details if business else q.bank_details,
        incoterm=q.incoterm,
        named_place=q.named_place,
        origin_port=q.origin_port,
        dest_port=q.dest_port,
        origin_country=origin_country,
        quantity_kg=q.quantity_kg,
        lines=q.lines,
        total_usd=q.total_usd,
        payment_text=q.payment.text,
        details=d,
        volume_m3=volume_m3(d),
        origin=origin,
        checklist=checklist,
        warnings=warnings,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def get(
    db: AsyncSession, http: httpx.AsyncClient, user: User, shipment_id: uuid.UUID
) -> Shipment:
    row = await db.scalar(
        select(ShipmentRow).where(ShipmentRow.id == shipment_id, ShipmentRow.user_id == user.id)
    )
    if row is None:
        raise NotFoundError("Shipment not found")
    return await render(db, http, user, row)


async def update_details(
    db: AsyncSession,
    http: httpx.AsyncClient,
    user: User,
    shipment_id: uuid.UUID,
    body: ShipmentPatch,
) -> Shipment:
    row = await db.scalar(
        select(ShipmentRow)
        .where(ShipmentRow.id == shipment_id, ShipmentRow.user_id == user.id)
        .with_for_update()
    )
    if row is None:
        await db.rollback()
        raise NotFoundError("Shipment not found")
    if row.version != body.version:
        await db.rollback()
        raise ConflictError("These documents were changed elsewhere. Reload to see the latest.")
    current = ShipmentDetails.model_validate(row.content.get("details") or {})
    changes = body.model_dump(include=body.model_fields_set - {"version"})
    merged = current.model_copy(update=changes)
    for text in ("consignee_address", "notify_party", "vessel", "voyage", "bl_number",
                 "containers", "seals", "final_destination", "package_size_cm", "marks",
                 "origin_criterion"):  # fmt: skip
        value = getattr(merged, text)
        if isinstance(value, str):
            setattr(merged, text, value.strip() or None)
    if merged != current:
        row.content = {**row.content, "details": merged.model_dump(mode="json")}
        row.version += 1
        row.updated_at = datetime.now(UTC)
    await db.commit()
    return await render(db, http, user, row)


async def list_shipments(db: AsyncSession, user: User) -> list[ShipmentSummary]:
    rows = await db.scalars(
        select(ShipmentRow)
        .where(ShipmentRow.user_id == user.id)
        .order_by(ShipmentRow.created_at.desc())
        .limit(200)
    )
    return [
        ShipmentSummary(
            id=r.id,
            invoice_number=r.invoice_number,
            buyer_name=r.buyer_name,
            market=r.market,
            total_usd=float(r.content["quote"]["total_usd"]),
            created_at=r.created_at,
        )
        for r in rows
    ]


async def remove(db: AsyncSession, user: User, shipment_id: uuid.UUID) -> None:
    result = await db.execute(
        delete(ShipmentRow)
        .where(ShipmentRow.id == shipment_id, ShipmentRow.user_id == user.id)
        .returning(ShipmentRow.id)
    )
    await db.commit()
    if result.first() is None:
        raise NotFoundError("Shipment not found")
