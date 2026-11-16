"""Alert emails behind a small `Sender` interface, so a provider can be plugged in later.

No email account exists yet, so nothing is ever sent:
- While `alerts_email_enabled` is off (the default), the alert job builds no messages
  and never reads an address.
- When it is on, the job hands each new notification to `get_sender()`, which returns
  `LogSender` until a real provider is written: it logs the subject and sends nothing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    text: str


class Sender(Protocol):
    async def send(self, message: EmailMessage) -> None:
        """Deliver one message or raise. Implementations must never log the address."""


class LogSender:
    """Sends nothing: notes that a message would have gone out (subject only)."""

    async def send(self, message: EmailMessage) -> None:
        log.info("Email delivery isn't set up; not sent: %s", message.subject)


def get_sender() -> Sender:
    """The sender alerts use. Only the logging one exists until there's an email account."""
    return LogSender()
