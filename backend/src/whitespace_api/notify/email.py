"""Outgoing email behind a small `Sender` interface.

`get_sender(settings)` returns `SmtpSender` when an SMTP account is configured
(`SMTP_USER` / `SMTP_PASSWORD`, e.g. Gmail with an app password), else `LogSender`,
which logs the subject and sends nothing. Senders never log the recipient's address.

Alerts additionally stay off until `alerts_email_enabled` is set.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage
from email.utils import formataddr, make_msgid
from typing import Protocol

from whitespace_api.core.config import Settings

log = logging.getLogger(__name__)
TIMEOUT_SECONDS = 20


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


class SmtpSender:
    """Plain-text mail over SMTP with STARTTLS (port 587) or TLS (port 465)."""

    def __init__(self, settings: Settings) -> None:
        assert settings.smtp_user and settings.smtp_password
        self.host, self.port = settings.smtp_host, settings.smtp_port
        self.user = settings.smtp_user
        self.password = settings.smtp_password.get_secret_value()
        self.sender = formataddr((settings.mail_from_name, settings.smtp_user))

    def _mime(self, message: EmailMessage) -> MimeMessage:
        mime = MimeMessage()
        mime["From"] = self.sender
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime["Message-ID"] = make_msgid(domain=self.user.rpartition("@")[2] or None)
        mime.set_content(message.text)
        return mime

    def _send(self, message: EmailMessage) -> None:
        context = ssl.create_default_context()
        if self.port == 465:
            with smtplib.SMTP_SSL(
                self.host, self.port, context=context, timeout=TIMEOUT_SECONDS
            ) as smtp:
                smtp.login(self.user, self.password)
                smtp.send_message(self._mime(message))
            return
        with smtplib.SMTP(self.host, self.port, timeout=TIMEOUT_SECONDS) as smtp:
            smtp.starttls(context=context)
            smtp.login(self.user, self.password)
            smtp.send_message(self._mime(message))

    async def send(self, message: EmailMessage) -> None:
        await asyncio.to_thread(self._send, message)


def get_sender(settings: Settings) -> Sender:
    return SmtpSender(settings) if settings.email_enabled else LogSender()
