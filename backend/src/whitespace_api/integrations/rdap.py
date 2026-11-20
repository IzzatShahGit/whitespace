"""When a domain was registered, from RDAP (the registries' public JSON service, which
replaced WHOIS). rdap.org redirects to the right registry. Free, no key. Some country
registries (e.g. .de) don't publish dates: that is "unknown", not a warning."""

from __future__ import annotations

from datetime import date

import httpx

RDAP_URL = "https://rdap.org/domain/{domain}"
TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class RdapError(RuntimeError):
    pass


async def registered_on(client: httpx.AsyncClient, domain: str) -> date | None:
    try:
        response = await client.get(
            RDAP_URL.format(domain=domain), timeout=TIMEOUT, follow_redirects=True
        )
        if response.status_code == 404:
            raise RdapError("not registered")
        response.raise_for_status()
        events = response.json().get("events", [])
    except (httpx.HTTPError, ValueError) as exc:
        raise RdapError(type(exc).__name__) from exc
    for event in events:
        if event.get("eventAction") == "registration" and event.get("eventDate"):
            try:
                return date.fromisoformat(str(event["eventDate"])[:10])
            except ValueError:
                return None
    return None
