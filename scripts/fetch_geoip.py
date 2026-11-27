"""Download DB-IP's free "IP to Country Lite" database (CC BY 4.0, updated monthly).

The API looks up a visitor's country in it (then drops the address). Standard library
only, so the API's Docker image can run it before any packages are installed.

    python scripts/fetch_geoip.py [out_path]     # default: data/geoip/country.mmdb

Tries this month's file, then last month's. Exits 1 if neither downloads; the API still
works without the file (visits just have no country).
"""

from __future__ import annotations

import gzip
import shutil
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

URL = "https://download.db-ip.com/free/dbip-country-lite-{month}.mmdb.gz"


def months() -> list[str]:
    now = datetime.now(UTC)
    last = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
    return [f"{now.year}-{now.month:02d}", f"{last[0]}-{last[1]:02d}"]


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "data/geoip/country.mmdb")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    for month in months():
        try:
            request = urllib.request.Request(  # noqa: S310 (a fixed https URL)
                URL.format(month=month), headers={"user-agent": "whitespace-geoip/1"}
            )
            with (
                urllib.request.urlopen(request, timeout=60) as response,  # noqa: S310
                gzip.GzipFile(fileobj=response) as source,
                tmp.open("wb") as target,
            ):
                shutil.copyfileobj(source, target)
        except OSError as exc:
            print(f"geoip: {month} not available ({exc})", file=sys.stderr)
            continue
        tmp.replace(out)
        print(f"geoip: saved {out} ({month}, {out.stat().st_size // 1024} KB)")
        return 0
    tmp.unlink(missing_ok=True)
    print("geoip: download failed; visits will have no country", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
