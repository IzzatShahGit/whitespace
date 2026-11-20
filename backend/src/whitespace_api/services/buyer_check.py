"""Is this buyer real, and safe to deal with? One check, every finding sourced.

What it looks at, all free public data or fixed rules (no model, so the same input
always gives the same answer):
- sanctions: the company name against the OFAC, UN, EU and UK lists (services.screening);
- country: places where payments are blocked or heavily restricted;
- register: the global legal-entity register (GLEIF), and the EU VAT register (VIES)
  when a VAT number is given;
- domains: how old the website is (RDAP), a free webmail address, an email domain that
  differs from the website or imitates it;
- wording: scam patterns in their emails (services.red_flags).

Verdict: red if anything serious, amber if anything to verify (or a check couldn't
run), green otherwise. It says whether a company is who it claims to be; it can't say
whether it will pay, and says so.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import asdict
from datetime import UTC, date, datetime
from difflib import SequenceMatcher
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.core.config import Settings
from whitespace_api.integrations import rdap
from whitespace_api.integrations.monthly_trade import EU_MEMBERS
from whitespace_api.models.pipeline import PipelineContact, PipelineMessage
from whitespace_api.models.screening import BuyerCheck
from whitespace_api.models.user import User
from whitespace_api.repositories import trade as trade_repo
from whitespace_api.repositories import usage as usage_repo
from whitespace_api.schemas.screening import (
    BuyerCheckOut,
    CheckIn,
    Finding,
    ListInfo,
    SanctionHit,
    Verdict,
)
from whitespace_api.services import pipeline, screening
from whitespace_api.services import tenders as registers
from whitespace_api.services.pipeline import LimitError, NotFoundError
from whitespace_api.services.red_flags import message_flags

CHECK_KIND = "check"
NEW_DOMAIN_DAYS = 180
VERY_NEW_DOMAIN_DAYS = 45
ESTABLISHED_DOMAIN_DAYS = 2 * 365
THREAD_MESSAGES = 10
# Where payments are blocked or heavily restricted (as of 2026-11; review with the lists).
HIGH_RISK_COUNTRIES = {
    "PRK": "North Korea is under comprehensive UN sanctions.",
    "IRN": "Iran is under UN, US, EU and UK sanctions; banks rarely process its payments.",
    "CUB": "Cuba is under a US embargo; payments through US banks or in dollars are blocked.",
    "RUS": "Russia is under wide EU, UK and US sanctions; many goods and banks are restricted.",
    "BLR": "Belarus is under wide EU, UK and US sanctions; many goods and banks are restricted.",
}
WEBMAIL = {
    "gmail.com", "googlemail.com", "yahoo.com", "ymail.com", "hotmail.com", "outlook.com",
    "live.com", "msn.com", "aol.com", "icloud.com", "me.com", "mail.com", "gmx.com",
    "gmx.net", "gmx.de", "web.de", "mail.ru", "yandex.ru", "yandex.com", "proton.me",
    "protonmail.com", "qq.com", "163.com", "126.com", "sina.com", "yeah.net",
    "rediffmail.com", "zoho.com", "yopmail.com", "inbox.com", "t-online.de",
}  # fmt: skip
WEBMAIL_BRANDS = ("yahoo", "hotmail", "outlook", "live")  # every country's domain
SECOND_LEVEL = {"co", "com", "net", "org", "gov", "ac", "edu", "or", "ne", "gob", "gen"}
RANK = {"high": 0, "medium": 1, "info": 2, "ok": 3}


# --- domains -------------------------------------------------------------------------


def registrable(host: str) -> str:
    """ "shop.hansen-textil.co.uk" -> "hansen-textil.co.uk" (good enough for the common
    second-level forms; no public-suffix list needed)."""
    labels = host.lower().strip(".").removeprefix("www.").split(".")
    if len(labels) >= 3 and labels[-2] in SECOND_LEVEL and len(labels[-1]) == 2:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def website_domain(url: str | None) -> str | None:
    if not url:
        return None
    host = urlparse(url if "://" in url else f"https://{url}").hostname
    return registrable(host) if host and "." in host else None


def email_domain(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    host = email.rsplit("@", 1)[1].strip().lower()
    return registrable(host) if "." in host else None


def is_webmail(domain: str) -> bool:
    return domain in WEBMAIL or domain.split(".")[0] in WEBMAIL_BRANDS


def lookalike(a: str, b: str) -> bool:
    """Different domains whose names are nearly the same: hansen-textil vs hansentextil."""
    if a == b:
        return False
    first_a, first_b = a.split(".")[0], b.split(".")[0]
    if first_a.replace("-", "") == first_b.replace("-", ""):
        return True
    return SequenceMatcher(None, first_a, first_b).ratio() >= 0.8


def _age_finding(domain: str, registered: date | None, today: date, *, what: str) -> Finding:
    if registered is None:
        return Finding(
            code="domain_unknown",
            severity="info",
            title=f"{what.capitalize()} age not published",
            detail=f"The registry for {domain} doesn't publish registration dates.",
        )
    days = (today - registered).days
    years = days // 365
    if days < VERY_NEW_DOMAIN_DAYS:
        return Finding(
            code="domain_new",
            severity="high",
            title=f"{what.capitalize()} registered {days} days ago",
            detail=f"{domain} was registered on {registered:%d %b %Y}. Scam buyers often use "
            "brand-new domains. Ask how long they've traded and check their references.",
        )
    if days < NEW_DOMAIN_DAYS:
        return Finding(
            code="domain_new",
            severity="medium",
            title=f"{what.capitalize()} registered {days // 30} months ago",
            detail=f"{domain} is new (registered {registered:%d %b %Y}). Fine for a new "
            "business, but worth asking about.",
        )
    return Finding(
        code="domain_age",
        severity="ok" if days >= ESTABLISHED_DOMAIN_DAYS else "info",
        title=f"{what.capitalize()} registered {years} year{'s' if years != 1 else ''} ago"
        if years
        else f"{what.capitalize()} registered {days // 30} months ago",
        detail=f"{domain} has existed since {registered:%d %b %Y}.",
    )


async def _registered_on(http: httpx.AsyncClient, domain: str) -> date | Exception | None:
    try:
        return await rdap.registered_on(http, domain)
    except rdap.RdapError as exc:
        return exc


# --- the check -----------------------------------------------------------------------


async def _nothing() -> list[Finding]:
    return []


def verdict(findings: list[Finding]) -> Verdict:
    severities = {f.severity for f in findings}
    return "red" if "high" in severities else "amber" if "medium" in severities else "green"


async def _sanctions(
    db: AsyncSession, name: str
) -> tuple[list[Finding], list[SanctionHit], list[ListInfo]]:
    lists = [ListInfo(**asdict(s)) for s in await screening.lists(db)]
    loaded = [entry for entry in lists if entry.names > 0]
    hits = [
        SanctionHit(
            source=m.source, source_label=m.source_label, name=m.name, program=m.program,
            url=m.url, grade=m.grade, score=m.score,
        )
        for m in await screening.screen(db, name)
    ]  # fmt: skip
    findings = []
    strong = [h for h in hits if h.grade == "strong"]
    if strong:
        h = strong[0]
        findings.append(
            Finding(
                code="sanctions_match",
                severity="high",
                title="Name matches a sanctioned party",
                detail=f"“{h.name}” is on the {h.source_label}"
                + (f" ({h.program})" if h.program else "")
                + ". Don't trade, ship or accept payment until you've confirmed it's a "
                "different company (address, registration number).",
                url=h.url,
            )
        )
    elif hits:
        h = hits[0]
        findings.append(
            Finding(
                code="sanctions_possible",
                severity="medium",
                title="Similar name on a sanctions list",
                detail=f"“{h.name}” on the {h.source_label} is close. Most such matches are "
                "different companies; compare the address and registration number.",
                url=h.url,
            )
        )
    if len(loaded) < len(lists):
        missing = ", ".join(entry.label for entry in lists if entry.names == 0)
        findings.append(
            Finding(
                code="sanctions_incomplete",
                severity="medium",
                title="Not every sanctions list could be checked",
                detail=f"Not loaded yet: {missing}. Try again later.",
            )
        )
    elif not hits:
        oldest = min((e.loaded_at for e in loaded if e.loaded_at), default=None)
        findings.append(
            Finding(
                code="sanctions_clear",
                severity="ok",
                title=f"Not on {len(loaded)} official sanctions lists",
                detail="Checked against "
                + ", ".join(e.label for e in loaded)
                + (f" (updated {oldest:%d %b %Y})." if oldest else "."),
            )
        )
    return findings, hits, lists


async def _register(
    db: AsyncSession, http: httpx.AsyncClient, name: str, country: str
) -> list[Finding]:
    found = await registers.check_company(db, http, name, country)
    if not found.available:
        return [
            Finding(
                code="register_unavailable",
                severity="info",
                title="Company register not reachable",
                detail="The global register (GLEIF) didn't answer. Try again later.",
            )
        ]
    exact = next((m for m in found.matches if m.exact), None)
    if exact is None:
        return [
            Finding(
                code="register_none",
                severity="info",
                title="Not in the global register of legal entities",
                detail="Common for smaller firms, which often have no LEI. Check the "
                "registration number on their website's legal notice instead.",
            )
        ]
    if not exact.active:
        return [
            Finding(
                code="register_inactive",
                severity="medium",
                title="Registered, but marked inactive",
                detail=f"{exact.name} is in the register as inactive. Ask whether the "
                "company still trades under this name.",
                url=exact.url,
            )
        ]
    return [
        Finding(
            code="register_found",
            severity="ok",
            title="Registered legal entity",
            detail=f"{exact.name}"
            + (f", {exact.city}" if exact.city else "")
            + (f" (reg. {exact.registered_as})" if exact.registered_as else "")
            + " is active in the global register (GLEIF).",
            url=exact.url,
        )
    ]


async def _vat(http: httpx.AsyncClient, country: str, number: str, name: str) -> list[Finding]:
    if country not in EU_MEMBERS:
        return []
    try:
        result = await registers.check_vat(http, country, number)
    except (registers.UnavailableError, registers.NotFoundError):
        return [
            Finding(
                code="vat_unavailable",
                severity="info",
                title="VAT register not reachable",
                detail="The EU VAT service didn't answer for this country. Try again later.",
            )
        ]
    if not result.valid:
        return [
            Finding(
                code="vat_invalid",
                severity="high",
                title="VAT number is not valid",
                detail=f"{result.number} isn't a valid EU VAT number. A real EU importer "
                "has one; ask them to confirm it.",
            )
        ]
    if (
        result.name
        and screening.similarity(screening.comparable(result.name), screening.comparable(name))
        < 0.6
    ):
        return [
            Finding(
                code="vat_other_name",
                severity="medium",
                title="VAT number belongs to a different name",
                detail=f"{result.number} is registered to “{result.name}”. Ask why.",
            )
        ]
    return [
        Finding(
            code="vat_valid",
            severity="ok",
            title="Valid EU VAT number",
            detail=f"{result.number}"
            + (f" is registered to {result.name}." if result.name else " is valid."),
        )
    ]


async def _domains(
    http: httpx.AsyncClient, site: str | None, mail: str | None, today: date
) -> list[Finding]:
    findings: list[Finding] = []
    if mail and is_webmail(mail):
        findings.append(
            Finding(
                code="webmail",
                severity="medium",
                title="Writes from a free email address",
                detail=f"They use {mail}. Many small firms do, but established importers "
                "usually write from their company domain. Ask for a company address.",
            )
        )
    elif mail and site and mail != site:
        if lookalike(mail, site):
            findings.append(
                Finding(
                    code="lookalike_domain",
                    severity="high",
                    title="Email domain imitates their website",
                    detail=f"Emails come from {mail} but the website is {site}. Fraudsters "
                    "register near-copies of real domains. Confirm by phone, using a "
                    "number from the real website.",
                )
            )
        else:
            findings.append(
                Finding(
                    code="domain_mismatch",
                    severity="medium",
                    title="Email domain differs from the website",
                    detail=f"Emails come from {mail}, the website is {site}. Sometimes "
                    "normal (a group domain), but worth asking.",
                )
            )
    targets = [(site, "website")] if site else []
    if mail and not is_webmail(mail) and mail != site:
        targets.append((mail, "email domain"))
    ages = await asyncio.gather(*(_registered_on(http, d) for d, _ in targets))
    for (domain, what), registered in zip(targets, ages, strict=True):
        if isinstance(registered, Exception):
            if str(registered) == "not registered":
                findings.append(
                    Finding(
                        code="domain_missing",
                        severity="high",
                        title=f"{what.capitalize()} isn't registered",
                        detail=f"{domain} doesn't exist in the domain registry.",
                    )
                )
            continue
        findings.append(_age_finding(domain, registered, today, what=what))
    return findings


async def _thread_texts(db: AsyncSession, contact_id: uuid.UUID) -> list[str]:
    rows = await db.scalars(
        select(PipelineMessage.body)
        .where(PipelineMessage.contact_id == contact_id, PipelineMessage.direction == "in")
        .order_by(PipelineMessage.created_at.desc())
        .limit(THREAD_MESSAGES)
    )
    return list(rows)


def _wording(texts: list[str]) -> list[Finding]:
    seen: dict[str, Finding] = {}
    for text in texts:
        for flag in message_flags(text):
            seen.setdefault(
                flag.code,
                Finding(
                    code=f"wording_{flag.code}",
                    severity=flag.severity,
                    title="Warning sign in their email",
                    detail=flag.label,
                    quote=flag.quote,
                ),
            )
    return list(seen.values())


async def check(
    db: AsyncSession, http: httpx.AsyncClient, user: User, body: CheckIn, settings: Settings
) -> BuyerCheckOut:
    contact: PipelineContact | None = None
    texts = [body.message] if body.message else []
    if body.contact_id:
        contact = await db.scalar(
            select(PipelineContact).where(
                PipelineContact.id == body.contact_id, PipelineContact.user_id == user.id
            )
        )
        if contact is None:
            raise NotFoundError("Not in your pipeline")
        texts += await _thread_texts(db, contact.id)
    if body.country not in await trade_repo.countries_by_code(db, [body.country]):
        raise NotFoundError(f"Unknown country {body.country}")
    count = await usage_repo.consume(
        db, user_id=user.id, kind=CHECK_KIND, day=date.today(),
        limit=settings.buyer_check_daily_limit,
    )  # fmt: skip
    if count is None:
        raise LimitError(
            f"You've used today's {settings.buyer_check_daily_limit} buyer checks. "
            "They reset tomorrow."
        )
    await db.commit()

    site = website_domain(body.website or (contact.website if contact else None))
    mail = email_domain(body.email)
    today = datetime.now(UTC).date()
    findings, hits, lists = await _sanctions(db, body.name)
    if body.country in HIGH_RISK_COUNTRIES:
        findings.append(
            Finding(
                code="country_restricted",
                severity="medium",
                title="Payments from this country are restricted",
                detail=HIGH_RISK_COUNTRIES[body.country]
                + " Check what you may sell and how you'd be paid before quoting.",
            )
        )
    findings += await _register(db, http, body.name, body.country)
    vat, domains = await asyncio.gather(
        _vat(http, body.country, body.vat, body.name) if body.vat else _nothing(),
        _domains(http, site, mail, today),
    )
    findings += vat + domains
    findings += _wording(texts)
    findings.sort(key=lambda f: RANK[f.severity])
    out = BuyerCheckOut(
        verdict=verdict(findings),
        findings=findings,
        sanctions=hits,
        lists=lists,
        name=body.name,
        country=body.country,
        website_domain=site,
        email_domain=mail,
        contact_id=contact.id if contact else None,
        checked_at=datetime.now(UTC),
    )
    if contact is not None:
        await _save(db, user, contact.id, out)
    return out


async def _save(db: AsyncSession, user: User, contact_id: uuid.UUID, out: BuyerCheckOut) -> None:
    values = {
        "verdict": out.verdict,
        "result": out.model_dump(mode="json"),
        "checked_at": out.checked_at,
    }
    await db.execute(
        insert(BuyerCheck)
        .values(contact_id=contact_id, **values)
        .on_conflict_do_update(index_elements=["contact_id"], set_=values)
    )
    row = await pipeline.lock(db, user, contact_id)
    words = {"green": "no warning signs", "amber": "things to verify", "red": "serious warnings"}
    pipeline.record(db, row, [("check", f"Buyer check: {words[out.verdict]}")])
    await db.commit()


async def latest(db: AsyncSession, user: User, contact_id: uuid.UUID) -> BuyerCheckOut:
    row = await db.scalar(
        select(BuyerCheck)
        .join(PipelineContact, PipelineContact.id == BuyerCheck.contact_id)
        .where(BuyerCheck.contact_id == contact_id, PipelineContact.user_id == user.id)
    )
    if row is None:
        raise NotFoundError("This company hasn't been checked yet")
    return BuyerCheckOut.model_validate(row.result)
