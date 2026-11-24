"""Checking a buyer's letter of credit or purchase order against your quote."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from tests.test_quotes import BASE, lane, offline  # noqa: F401  (fixtures)
from whitespace_api.agents.llm import CallSpec
from whitespace_api.core.config import Settings, get_settings
from whitespace_api.integrations import swift
from whitespace_api.main import app
from whitespace_api.services import doc_check

RAW = AIMessage(content="", response_metadata={"model_name": "fake"})
SOON = datetime.now(UTC).date() + timedelta(days=40)


def yymmdd(d: date) -> str:
    return f"{d:%y%m%d}"


MT700 = f"""
:27: 1/1
:40A: IRREVOCABLE
:20: LC-DE-2026-0815
:31C: {yymmdd(SOON - timedelta(days=60))}
:40E: UCP LATEST VERSION
:31D: {yymmdd(SOON + timedelta(days=10))}GERMANY
:50: HOLIDAY HEIMTEX GMBH
     WIESENSTR. 5, BREMEN
:59: /PK12ABCD0000001
     AHMED TOWELS
:32B: USD40000,00
:39A: 05/05
:41D: ANY BANK BY NEGOTIATION
:42C: 60 DAYS AFTER B/L DATE
:43P: NOT ALLOWED
:43T: ALLOWED
:44E: KARACHI
:44F: HAMBURG
:44C: {yymmdd(SOON)}
:45A: 9,280 KGS COTTON TERRY TOWELS AS PER PROFORMA NO 7
      FOB KARACHI INCOTERMS 2020
:46A: + SIGNED COMMERCIAL INVOICE IN 3 ORIGINALS
      + FULL SET CLEAN ON BOARD BILLS OF LADING
      + INSPECTION CERTIFICATE SIGNED BY THE APPLICANT
:47A: + ALL DOCUMENTS MUST SHOW THE LC NUMBER
:48: 21 DAYS AFTER THE DATE OF SHIPMENT
:49: WITHOUT
:52A: DEUTSCHE BANK AG
"""


def test_swift_fields_are_read_exactly() -> None:
    assert swift.is_mt700(MT700) and not swift.is_mt700("Dear sir, :20: is a time")
    terms, quotes = doc_check.read_swift(MT700)
    assert terms.number == "LC-DE-2026-0815" and terms.buyer == "HOLIDAY HEIMTEX GMBH"
    assert terms.seller == "AHMED TOWELS"  # the account line is skipped
    assert (terms.currency, terms.amount, terms.tolerance_pct) == ("USD", 40000.0, 5.0)
    assert (terms.incoterm, terms.named_place) == ("FOB", "KARACHI")
    assert (terms.quantity, terms.unit) == (9280.0, "KGS")
    assert terms.latest_shipment == SOON and terms.expiry == SOON + timedelta(days=10)
    assert terms.presentation_days == 21 and terms.revocable is False
    assert terms.payment == "ANY BANK BY NEGOTIATION 60 DAYS AFTER B/L DATE"
    assert terms.documents[2] == "INSPECTION CERTIFICATE SIGNED BY THE APPLICANT"
    assert quotes["amount"] == ":32B:USD40000,00"
    assert swift.incoterm("CIF HAMBURG AS PER INCOTERMS 2020") == ("CIF", "HAMBURG")
    assert swift.quantity("18.560 KGS") == (18560.0, "KGS")
    assert swift.swift_amount("EUR1.250,50") == ("EUR", 1250.5)


def test_rules_catch_soft_clauses_and_squeezed_dates() -> None:
    terms, _ = doc_check.read_swift(MT700)
    today = datetime.now(UTC).date()
    codes = {f.code for f in doc_check._date_findings(terms, today)}
    assert codes == {"presentation_squeezed"}  # 10 days between shipment and expiry
    clauses = doc_check._clause_findings(MT700)
    assert [f.code for f in clauses] == ["clause_applicant_document"]
    assert "SIGNED BY THE APPLICANT" in (clauses[0].quote or "")
    assert doc_check._clause_findings("PAYMENT AFTER ARRIVAL OF THE GOODS AT DESTINATION")
    assert not doc_check._clause_findings("This credit is irrevocable and confirmed.")
    named = doc_check._buyer_signs(
        "Inspection certificate to be issued by Holiday Heimtex quality department.",
        "Holiday Heimtex GmbH & Co. KG",
    )
    assert named is not None and named.severity == "high"
    assert doc_check._buyer_signs("Certificate issued by SGS Pakistan.", "Holiday Heimtex") is None


@pytest.fixture
def no_model(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[Any]]:
    calls: list[Any] = []

    def fake(spec: CallSpec, settings: Any = None) -> Any:
        def run(messages: Any) -> Any:
            calls.append(messages[-1][1])
            read = doc_check._Read(
                kind="purchase_order",
                number=doc_check._Val(value="PO-4471", quote="Order no. PO-4471"),
                buyer=doc_check._Val(value="Holiday Heimtex GmbH", quote="Holiday Heimtex GmbH"),
                amount=doc_check._Val(value="46400", quote="Total: USD 46,400.00"),
                currency=doc_check._Val(value="USD", quote="USD 46,400.00"),
                incoterm=doc_check._Val(value="CIF", quote="CIF Hamburg"),
                latest_shipment=doc_check._Val(
                    value=f"{SOON:%Y-%m-%d}", quote=f"Ship by {SOON:%d %B %Y}"
                ),
                payment=doc_check._Val(value="Open account 90 days", quote="the moon"),
                conditions=["Payment after arrival of the goods", "Not in the order at all"],
            )
            return {"raw": RAW, "parsed": read}

        return RunnableLambda(run)

    monkeypatch.setattr(doc_check.llm, "get_chat_model", fake)
    yield calls


PO_TEXT = (
    "PURCHASE ORDER  Order no. PO-4471\nBuyer: Holiday Heimtex GmbH, Bremen\n"
    "Supplier: Ahmed Towels, Karachi\n9,280 kg terry towels, CIF Hamburg\n"
    f"Total: USD 46,400.00\nShip by {SOON:%d %B %Y}\nPayment after arrival of the goods\n"
)


async def test_swift_needs_no_model_and_compares_with_the_quote(
    user: AsyncClient,
    lane: None,  # noqa: F811
    no_model: list[Any],
) -> None:
    quote = (await user.post("/api/v1/quotes", json=BASE | {"incoterm": "CIF"})).json()
    out = await user.post("/api/v1/documents/check", data={"text": MT700, "quote_id": quote["id"]})
    assert out.status_code == 200, out.text
    body = out.json()
    assert body["read_by"] == "swift" and no_model == []  # read in code
    assert body["verdict"] == "red" and body["quote_number"] == quote["number"]
    codes = [f["code"] for f in body["findings"]]
    assert {"clause_applicant_document", "incoterm", "amount_short", "presentation_squeezed",
            "seller_name", "unconfirmed"} <= set(codes)  # fmt: skip
    assert "quantity" not in codes  # 9,280 kg as quoted
    labels = {f["label"]: f["value"] for f in body["fields"]}
    assert labels["Amount"] == "USD 40,000.00" and labels["Incoterm"] == "FOB KARACHI"


async def test_model_reading_keeps_only_quoted_values(
    user: AsyncClient,
    lane: None,  # noqa: F811
    no_model: list[Any],
) -> None:
    quote = (await user.post("/api/v1/quotes", json=BASE)).json()  # FOB, 46,400
    out = await user.post(
        "/api/v1/documents/check", data={"text": PO_TEXT, "quote_id": quote["id"]}
    )
    body = out.json()
    assert body["read_by"] == "ai" and body["kind"] == "purchase_order"
    assert body["removed"] == 2  # the payment quote and one condition aren't in the PO
    assert body["terms"]["payment"] is None
    assert body["terms"]["conditions"] == ["Payment after arrival of the goods"]
    assert body["terms"]["latest_shipment"] == str(SOON)
    codes = [f["code"] for f in body["findings"]]
    assert "clause_after_goods" in codes and "removed" in codes
    assert "amount_short" not in codes  # 46,400 matches the quote
    assert "incoterm" in codes  # the PO says CIF, the quote FOB


async def test_pdf_scan_limits_and_privacy(user: AsyncClient, no_model: list[Any]) -> None:
    bad = await user.post(
        "/api/v1/documents/check", files={"file": ("x.pdf", b"hello", "application/pdf")}
    )
    assert bad.status_code == 422 and "PDF" in bad.json()["detail"]
    blank = minimal_pdf("")
    scan = await user.post(
        "/api/v1/documents/check", files={"file": ("scan.pdf", blank, "application/pdf")}
    )
    assert scan.status_code == 200 and scan.json()["read_by"] == "ai_scan"
    assert isinstance(no_model[-1], list) and no_model[-1][1]["mime_type"] == "application/pdf"
    assert "scanned" in [f["code"] for f in scan.json()["findings"]]

    text = minimal_pdf("PURCHASE ORDER " * 30)
    assert doc_check.pdf_text(text)[0].count("PURCHASE ORDER") == 30

    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,  # type: ignore[call-arg]
        doc_check_daily_limit=2,  # the scan above used one
    )
    try:
        first = await user.post("/api/v1/documents/check", data={"text": PO_TEXT})
        assert first.status_code == 200
        assert (
            await user.post("/api/v1/documents/check", data={"text": PO_TEXT})
        ).status_code == 429
        # SWIFT text never uses the allowance.
        assert (await user.post("/api/v1/documents/check", data={"text": MT700})).status_code == 200
    finally:
        app.dependency_overrides.pop(get_settings, None)
    other = await user.post(
        "/api/v1/documents/check",
        data={"text": MT700, "quote_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert other.status_code == 404


def minimal_pdf(text: str) -> bytes:
    """A one-page PDF with `text` on it (empty text: a page with no text layer)."""
    stream = f"BT /F1 12 Tf 20 700 Td ({text}) Tj ET".encode() if text else b""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return out


@pytest.mark.parametrize(
    ("value", "quote", "kept"),
    [
        ("2027-01-03", "Ship by 03 January 2027", True),  # leading zero on the day
        ("2027-01-03", "Ship by 3 Jan 27", True),
        ("2027-01-13", "Ship by 03 January 2027", False),  # a different day
        ("2027-01-03", "Ship by 03 January 2026", False),  # a different year
    ],
)
def test_dates_must_match_the_quote(value: str, quote: str, kept: bool) -> None:
    val = doc_check._Val(value=value, quote=quote)
    assert doc_check._supported("latest_shipment", val, quote) is kept
