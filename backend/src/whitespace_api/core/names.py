"""Company names compared the way people mean them: "MÖVE GmbH." is "move".

One set of rules for every place that matches names: lead lists (is the name on the
cited page?), the pipeline (is this company saved already?), tenders and sanctions
screening.
"""

from __future__ import annotations

import re
import unicodedata

# Dropped from the end of a name: "Hansen Textil GmbH & Co. KG" -> "hansen textil".
LEGAL_SUFFIXES = {
    "gmbh", "ltd", "limited", "inc", "llc", "co", "corp", "corporation", "company", "plc",
    "pvt", "private", "sa", "sas", "sarl", "srl", "spa", "bv", "nv", "ag", "kg", "ab", "oy",
    "as", "aps", "pty", "pte", "sdn", "bhd", "jsc", "ooo", "llp", "lda", "ltda", "sl", "kk",
    "tic", "san", "ve", "s", "p", "a", "l", "k", "rt", "zrt", "nyrt", "kft", "tbk",
}  # fmt: skip
# Legal forms written first: "JSC Sovcomflot", "PT Indofood", "OOO Romashka".
LEGAL_PREFIXES = {
    "jsc", "pjsc", "ojsc", "cjsc", "pao", "oao", "zao", "ooo", "ao", "tov", "pt", "cv",
}  # fmt: skip


def norm(text: str) -> str:
    """Casefolded words without accents or punctuation: "MÖVE GmbH." -> "move gmbh"."""
    plain = "".join(
        ch for ch in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(ch)
    )
    return " ".join(re.sub(r"[\W_]+", " ", plain).split())


def core_name(name: str) -> str:
    """ "The Hansen Textil GmbH & Co. KG" -> "hansen textil": the part that identifies it."""
    tokens = norm(name).split()
    while tokens and tokens[-1] in LEGAL_SUFFIXES:
        tokens.pop()
    for prefix in (["the"], ["m", "s"], ["messrs"]):  # "M/s. Al-Karam" is "Al-Karam"
        if tokens[: len(prefix)] == prefix:
            tokens = tokens[len(prefix) :]
    while len(tokens) > 1 and tokens[0] in LEGAL_PREFIXES:
        tokens.pop(0)
    return " ".join(tokens)
