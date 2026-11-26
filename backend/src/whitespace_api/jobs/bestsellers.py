"""Amazon best-seller lists: `python -m whitespace_api.jobs.bestsellers [--now]`.

Runs hourly in the app (it only starts an Apify run once a week). By hand, it saves any
finished run; `--now` also starts a new one straight away (it takes a few minutes; run
this again afterwards to save it).
"""

from __future__ import annotations

import asyncio
import logging
import sys

from whitespace_api.core.config import Settings, get_settings
from whitespace_api.services import bestsellers


async def run(settings: Settings, *, force: bool = False) -> str:
    return await bestsellers.run(settings, force=force)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(asyncio.run(run(get_settings(), force="--now" in sys.argv)))
