"""Everyday product names -> HS codes.

Customs descriptions use technical wording: footballs are "Balls: inflatable", bed sheets
are "Bed linen". People search with everyday words, so these aliases map common names
(as exporters in the covered countries say them) to the codes they mean. Values are
six-digit codes or shorter prefixes ("6115" = every sock product).

Order matters: when several names fit one product equally, the earlier one is used as
its everyday name (e.g. in search phrases), so list the most common name first.

Matching is word-based and forgiving about plurals: "cricket balls" matches
"cricket ball". When several aliases match, only the most specific ones are used, so
"ball bearings" means bearings, not footballs.
"""

from __future__ import annotations

import re

ALIASES: dict[str, tuple[str, ...]] = {
    # Sports goods
    "ball": ("950662", "950669", "950661"),
    "sports ball": ("950662", "950669", "950661"),
    "football": ("950662",),
    "soccer ball": ("950662",),
    "volleyball": ("950662",),
    "basketball": ("950662",),
    "rugby ball": ("950662",),
    "handball": ("950662",),
    "cricket ball": ("950669",),
    "hockey ball": ("950669",),
    "baseball": ("950669",),
    "softball": ("950669",),
    "tennis ball": ("950661",),
    "golf ball": ("950632",),
    "cricket bat": ("950699",),
    "hockey stick": ("950699",),
    "cricket": ("950669", "950699"),
    "racket": ("950651", "950659"),
    "racquet": ("950651", "950659"),
    "badminton": ("950659",),
    "boxing glove": ("950691",),
    "gym equipment": ("950691",),
    "fitness equipment": ("950691",),
    "sports glove": ("420321", "611610"),
    "goalkeeper glove": ("420321", "611610"),
    # Apparel and textiles
    "sock": ("6115",),
    "t shirt": ("6109",),
    "tshirt": ("6109",),
    "tee": ("6109",),
    "polo shirt": ("610510", "610520", "610590"),
    "shirt": ("6105", "6205"),
    "jean": ("620342", "620462"),
    "denim": ("620342", "620462", "520942"),
    "denim fabric": ("520942", "520943"),
    "trouser": ("620342", "620343", "620462", "620463"),
    "hoodie": ("6110",),
    "sweatshirt": ("6110",),
    "sweater": ("6110",),
    "jacket": ("6201", "6202", "420310"),
    "leather jacket": ("420310",),
    "leather glove": ("420321", "420329"),
    "glove": ("4203", "6116", "4015"),
    "workwear": ("6203", "6211"),
    "tracksuit": ("6112", "6211"),
    "sportswear": ("6112", "6211"),
    "baby clothe": ("6111", "6209"),
    "towel": ("630260", "630291"),
    "bed sheet": ("630221", "630231", "630232", "630239"),
    "bedsheet": ("630221", "630231", "630232", "630239"),
    "bed linen": ("6302",),
    "pillow cover": ("630231", "630221"),
    "curtain": ("6303",),
    "home textile": ("6302", "6303", "6304"),
    "yarn": ("5205", "5206"),
    "cotton yarn": ("5205",),
    "carpet": ("57",),
    "rug": ("57",),
    "handbag": ("420221", "420222", "420229"),
    "bag": ("4202",),
    "shoe": ("64",),
    "sneaker": ("640411", "640419"),
    "footwear": ("64",),
    # Food and agriculture
    "rice": ("1006",),
    "basmati rice": ("100630",),
    "basmati": ("100630",),
    "mango": ("080450",),
    "date": ("080410",),
    "kinnow": ("080521", "080522"),
    "mandarin": ("080521", "080522"),
    "orange": ("080510",),
    "pink salt": ("250100",),
    "himalayan salt": ("250100",),
    "salt": ("250100",),
    "sesame": ("120740",),
    "chilli": ("090421", "090422"),
    "chili": ("090421", "090422"),
    "cumin": ("090931", "090932"),
    "turmeric": ("091030",),
    "tea": ("0902",),
    "coffee": ("0901",),
    "shrimp": ("030616", "030617", "160521", "160529"),
    "prawn": ("030616", "030617", "160521", "160529"),
    "fish": ("03",),
    "seafood": ("03", "1605"),
    "onion": ("070310",),
    "potato": ("070190",),
    "cashew": ("080131", "080132"),
    "almond": ("080211", "080212"),
    "honey": ("040900",),
    "halal meat": ("0201", "0202", "0204"),
    "beef": ("0201", "0202"),
    "mutton": ("0204",),
    "chicken": ("0207",),
    # Manufactured goods and materials
    "surgical instrument": ("901890",),
    "surgical": ("9018",),
    "dental instrument": ("901841", "901849"),
    "medical device": ("9018", "9019", "9021"),
    "scissor": ("821300",),
    "knife": ("8211",),
    "cutlery": ("8211", "8215"),
    "medicine": ("3004",),
    "pharmaceutical": ("3004", "3003"),
    "plastic bag": ("392321", "392329"),
    "plastic packaging": ("3923",),
    "packaging": ("3923", "4819"),
    "carton": ("4819",),
    "cement": ("252321", "252329"),
    "marble": ("680221", "680291"),
    "granite": ("680293", "251611"),
    "ceramic tile": ("6907",),
    "tile": ("6907",),
    "furniture": ("9401", "9403"),
    "steel pipe": ("7304", "7305", "7306"),
    "copper wire": ("7408",),
    "cable": ("8544",),
    "ball bearing": ("848210",),
    "bearing": ("8482",),
}

_WORD = re.compile(r"[a-z0-9]+")


def _stem(word: str) -> str:
    """Rough singular form, enough for product names: balls->ball, boxes->box, shoes->shoe."""
    if len(word) > 4 and word.endswith(("ches", "shes", "sses", "xes")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def words(text: str) -> tuple[str, ...]:
    """Lower-cased, singularised words; hyphens and punctuation split words ("t-shirts")."""
    return tuple(_stem(w) for w in _WORD.findall(text.lower()))


_ALIAS_WORDS: dict[str, frozenset[str]] = {alias: frozenset(words(alias)) for alias in ALIASES}


def match_aliases(query: str) -> list[str]:
    """Aliases whose words all appear in the query, most specific first.

    An alias is dropped when another matched alias contains all of its words
    ("ball" is dropped when "cricket ball" also matches).
    """
    query_words = frozenset(words(query))
    matched = [a for a, ws in _ALIAS_WORDS.items() if ws and ws <= query_words]
    specific = [a for a in matched if not any(_ALIAS_WORDS[a] < _ALIAS_WORDS[b] for b in matched)]
    return sorted(specific, key=lambda a: -len(_ALIAS_WORDS[a]))


def codes_for(query: str) -> list[str]:
    """HS codes/prefixes the query's aliases point to, in order, without repeats."""
    return list(dict.fromkeys(code for alias in match_aliases(query) for code in ALIASES[alias]))
