"""Country from an IP address, using DB-IP's free country database (CC BY 4.0).

Only the two-letter country is kept; the address itself is never stored. Without the
database file every lookup returns None (`make geoip` downloads it).
"""

from __future__ import annotations

import ipaddress
import logging
from functools import cache
from pathlib import Path
from typing import Any

import maxminddb

log = logging.getLogger(__name__)
_REPO = Path(__file__).resolve().parents[4]  # backend/src/whitespace_api/services -> repo


@cache
def _reader(path: str) -> Any:
    candidates = [Path(path)] if Path(path).is_absolute() else [Path(path), _REPO / path]
    for candidate in candidates:
        if candidate.is_file():
            log.info("geoip: using %s", candidate.name)
            return maxminddb.open_database(str(candidate))
    log.warning("geoip: %s not found; visits will have no country (run `make geoip`)", path)
    return None


def country(address: str, path: str) -> str | None:
    """'39.32.0.1' -> 'PK'. None for private, invalid or unknown addresses."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return None
    if not ip.is_global:
        return None
    reader = _reader(path)
    if reader is None:
        return None
    try:
        found = reader.get(str(ip))
    except (ValueError, maxminddb.InvalidDatabaseError):
        return None
    code = (found or {}).get("country", {}).get("iso_code")
    return code if isinstance(code, str) and len(code) == 2 and code != "ZZ" else None
