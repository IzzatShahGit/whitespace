"""Public company registers: GLEIF (legal entities worldwide) and VIES (EU VAT numbers).
Both free, no key. Results describe registration only, never creditworthiness."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import httpx

GLEIF_URL = "https://api.gleif.org/api/v1/lei-records"
VIES_URL = "https://ec.europa.eu/taxation_customs/vies/rest-api/check-vat-number"
TIMEOUT = httpx.Timeout(15.0, connect=5.0)


class RegisterError(RuntimeError):
    pass


@dataclass(frozen=True)
class LeiRecord:
    lei: str
    name: str
    city: str | None
    country: str  # ISO alpha-2
    entity_status: str  # ACTIVE | INACTIVE
    registration_status: str  # ISSUED | LAPSED | RETIRED | ...
    registered_as: str | None  # the local registry number, e.g. "HRA 707389"
    next_renewal: date | None

    @property
    def url(self) -> str:
        return f"https://search.gleif.org/#/record/{self.lei}"


async def find_lei(client: httpx.AsyncClient, name: str, country_iso2: str) -> list[LeiRecord]:
    params = {
        "filter[fulltext]": name,
        "filter[entity.legalAddress.country]": country_iso2,
        "page[size]": "5",
    }
    try:
        response = await client.get(GLEIF_URL, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        rows = response.json().get("data", [])
    except (httpx.HTTPError, ValueError) as exc:
        raise RegisterError(f"GLEIF: {type(exc).__name__}") from exc
    out = []
    for row in rows:
        a = row.get("attributes", {})
        entity, registration = a.get("entity", {}), a.get("registration", {})
        renewal = (registration.get("nextRenewalDate") or "")[:10]
        out.append(
            LeiRecord(
                lei=a.get("lei", ""),
                name=(entity.get("legalName") or {}).get("name", ""),
                city=(entity.get("legalAddress") or {}).get("city"),
                country=(entity.get("legalAddress") or {}).get("country", country_iso2),
                entity_status=entity.get("status", ""),
                registration_status=registration.get("status", ""),
                registered_as=entity.get("registeredAs"),
                next_renewal=date.fromisoformat(renewal) if renewal else None,
            )
        )
    return out


@dataclass(frozen=True)
class VatResult:
    valid: bool
    name: str | None
    address: str | None


def _known(value: object) -> str | None:
    text = str(value or "").strip()
    return None if text in ("", "---") else text


async def check_vat(client: httpx.AsyncClient, country: str, number: str) -> VatResult:
    """`country` is the VIES code (EL for Greece). Some countries never return the name."""
    try:
        response = await client.post(
            VIES_URL, json={"countryCode": country, "vatNumber": number}, timeout=TIMEOUT
        )
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RegisterError(f"VIES: {type(exc).__name__}") from exc
    if "valid" not in body:  # e.g. the member state's service is down
        raise RegisterError(f"VIES: {body.get('errorWrappers') or 'no answer'}")
    return VatResult(
        valid=bool(body["valid"]),
        name=_known(body.get("name")),
        address=_known(body.get("address")),
    )
