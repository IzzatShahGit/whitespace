from __future__ import annotations

import logging
import re

# Query parameters that must never reach logs (OAuth codes, state, tokens).
_SENSITIVE = re.compile(r"([?&](?:code|state|token|access_token|id_token)=)[^&\s]+")


def redact(text: str) -> str:
    return _SENSITIVE.sub(r"\1[redacted]", text)


class RedactQueryFilter(logging.Filter):
    """Masks sensitive query values in uvicorn's access log lines."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(redact(a) if isinstance(a, str) else a for a in record.args)
        return True


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # httpx logs every outbound URL at INFO, and some APIs (Census) take their key as a
    # query parameter: keep outbound request lines out of the logs entirely.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, RedactQueryFilter) for f in access.filters):
        access.addFilter(RedactQueryFilter())
