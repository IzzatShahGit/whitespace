"""Warning signs in a message from a buyer: the wording trade scams are made of.

Plain rules, no model: the same text always gives the same flags, each flag quotes the
words that raised it, and a new pattern is one line. These cover the frauds exporters
actually meet: advance fees, changed bank details, untraceable payment, overpayment
refunds, phishing links and kickbacks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Severity = Literal["high", "medium"]


@dataclass(frozen=True)
class Rule:
    code: str
    severity: Severity
    label: str
    pattern: re.Pattern[str]


def _rx(*alternatives: str) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{a})" for a in alternatives), re.IGNORECASE)


RULES: tuple[Rule, ...] = (
    Rule(
        "advance_fee",
        "high",
        "Asks you to pay a fee before they buy. Real importers don't charge suppliers "
        "registration, licence or inspection fees.",
        _rx(
            r"\b(?:registration|processing|certification|membership|licen[cs]e|clearance|"
            r"handling|inspection|approval|vendor|supplier)\s+(?:fee|charge|cost)s?\b",
            r"\bpay\s+(?:a|the|our)\s+(?:small\s+)?(?:fee|charge|deposit)\b",
            r"\bfee\s+(?:must|should|has to)\s+be\s+paid\b",
        ),
    ),
    Rule(
        "bank_change",
        "high",
        "Says bank details have changed. The most common invoice fraud: confirm by phone "
        "on a number you already had before paying or shipping.",
        _rx(
            r"\b(?:new|changed|updated|different|alternative)\s+(?:bank|account|beneficiary)",
            r"\b(?:bank|account)\s+(?:details\s+)?(?:has|have)\s+(?:been\s+)?changed\b",
            r"\bdo\s+not\s+(?:pay|send|use)\s+(?:to\s+)?(?:the\s+)?(?:old|previous)\s+account\b",
        ),
    ),
    Rule(
        "untraceable_payment",
        "high",
        "Mentions a payment method that can't be traced or reversed.",
        _rx(
            r"\bwestern\s+union\b",
            r"\bmoney\s*gram\b",
            r"\bgift\s+cards?\b",
            r"\b(?:bitcoin|btc|usdt|tether|crypto(?:currency)?)\b",
        ),
    ),
    Rule(
        "overpayment",
        "high",
        "Talks about paying too much and asking for the difference back: a classic "
        "fake-cheque scam.",
        _rx(
            r"\b(?:overpa(?:y|id|yment)|excess\s+(?:amount|payment))\b",
            r"\b(?:refund|return|send\s+back)\s+the\s+(?:difference|balance|excess)\b",
        ),
    ),
    Rule(
        "phishing_link",
        "high",
        "Asks you to sign in or open a link to see the order. Order details come as an "
        "attachment or in the email, never behind a login.",
        _rx(
            r"\b(?:log\s*in|sign\s*in|login)\s+(?:to|with)\s+(?:view|see|download|access|"
            r"your)\b",
            r"\bclick\s+(?:here|the\s+link|below)\s+to\s+(?:view|download|see|open)\b",
            r"\bverify\s+your\s+(?:account|email|password)\b",
            r"https?://\S+\.(?:html?|php|exe|zip|scr)\b",
        ),
    ),
    Rule(
        "kickback",
        "high",
        "Asks for a personal commission or a payment to an individual.",
        _rx(
            r"\bcommission\s+(?:to|for)\s+(?:me|myself|our\s+(?:purchasing|procurement)\s+"
            r"(?:manager|officer|agent))\b",
            r"\b(?:personal|private)\s+(?:commission|account)\b",
        ),
    ),
    Rule(
        "pressure",
        "medium",
        "Pushes for speed. Pressure to skip checks is a common scam tactic. Take the time "
        "to verify.",
        _rx(
            r"\b(?:urgent(?:ly)?|immediately|asap)\b.{0,40}\b(?:pay|payment|transfer|ship|"
            r"send|confirm)\w*",
            r"\bwithin\s+(?:24|48)\s+hours\b",
            r"\bfinal\s+(?:notice|warning)\b",
        ),
    ),
    Rule(
        "unclear_order",
        "medium",
        "A large order with no product details or specifications. Real buyers ask about "
        "specs, prices and samples first.",
        _rx(
            r"\b(?:huge|large|big|bulk)\s+(?:order|quantity|purchase)\b.{0,60}"
            r"\b(?:any|all)\s+(?:of\s+)?(?:your\s+)?products?\b",
            r"\bwe\s+(?:will|want\s+to)\s+buy\s+(?:all|everything|any)\b",
        ),
    ),
)


@dataclass(frozen=True)
class Flag:
    code: str
    severity: Severity
    label: str
    quote: str


def _quote(text: str, match: re.Match[str], margin: int = 40) -> str:
    start, end = max(0, match.start() - margin), min(len(text), match.end() + margin)
    snippet = " ".join(text[start:end].split())
    return f"{'…' if start else ''}{snippet}{'…' if end < len(text) else ''}"


def message_flags(text: str) -> list[Flag]:
    """Each rule that matches, once, with the words around its first match."""
    flags = []
    for rule in RULES:
        match = rule.pattern.search(text)
        if match:
            flags.append(Flag(rule.code, rule.severity, rule.label, _quote(text, match)))
    return flags
