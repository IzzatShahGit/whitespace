"""Which language to write business email in, per market.

The first language listed is the one a cold email does best in. Where business is
mostly done in English even though another language is official (UAE, Malaysia,
India, ...), English comes first and the local language is offered second. Markets
not listed default to English.
"""

from __future__ import annotations

# ISO 639-1 (plus script/region where it matters) -> English name, for prompts and menus.
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "ar": "Arabic",
    "bg": "Bulgarian",
    "bn": "Bengali",
    "cs": "Czech",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "es": "Spanish",
    "et": "Estonian",
    "fa": "Persian",
    "fi": "Finnish",
    "fr": "French",
    "he": "Hebrew",
    "hr": "Croatian",
    "hu": "Hungarian",
    "id": "Indonesian",
    "it": "Italian",
    "ja": "Japanese",
    "km": "Khmer",
    "ko": "Korean",
    "lt": "Lithuanian",
    "lv": "Latvian",
    "ms": "Malay",
    "nb": "Norwegian",
    "nl": "Dutch",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "sr": "Serbian",
    "sv": "Swedish",
    "sw": "Swahili",
    "th": "Thai",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "ur": "Urdu",
    "uz": "Uzbek",
    "vi": "Vietnamese",
    "zh-CN": "Chinese (Simplified)",
    "zh-TW": "Chinese (Traditional)",
}

_SPANISH = "ARG BOL CHL COL CRI CUB DOM ECU ESP GTM HND MEX NIC PAN PER PRY SLV URY VEN"
_ARABIC_FIRST = "DZA EGY IRQ JOR LBY SAU SDN SYR YEM"
_GULF = "ARE BHR KWT OMN QAT"  # business email is mostly English
_ENGLISH = "AUS BGD CAN GBR GHA HKG IND IRL KEN LKA MYS NGA NPL NZL PAK PHL SGP UGA USA ZAF ZMB ZWE"

MARKET_LANGUAGES: dict[str, tuple[str, ...]] = {
    **dict.fromkeys(_SPANISH.split(), ("es",)),
    **dict.fromkeys(_ARABIC_FIRST.split(), ("ar",)),
    **dict.fromkeys(_GULF.split(), ("en", "ar")),
    **dict.fromkeys(_ENGLISH.split(), ("en",)),
    "AUT": ("de",),
    "DEU": ("de",),
    "CHE": ("de", "fr", "it"),
    "LIE": ("de",),
    "FRA": ("fr",),
    "BEL": ("nl", "fr"),
    "LUX": ("fr", "de"),
    "MCO": ("fr",),
    "NLD": ("nl",),
    "ITA": ("it",),
    "PRT": ("pt",),
    "BRA": ("pt",),
    "AGO": ("pt",),
    "MOZ": ("pt",),
    "POL": ("pl",),
    "CZE": ("cs",),
    "SVK": ("sk",),
    "HUN": ("hu",),
    "ROU": ("ro",),
    "MDA": ("ro", "ru"),
    "BGR": ("bg",),
    "GRC": ("el",),
    "CYP": ("el", "en"),
    "HRV": ("hr",),
    "SVN": ("sl",),
    "SRB": ("sr",),
    "SWE": ("sv",),
    "NOR": ("nb",),
    "DNK": ("da",),
    "FIN": ("fi",),
    "EST": ("et",),
    "LVA": ("lv",),
    "LTU": ("lt",),
    "RUS": ("ru",),
    "BLR": ("ru",),
    "KAZ": ("ru",),
    "KGZ": ("ru",),
    "UZB": ("ru", "uz"),
    "UKR": ("uk",),
    "TUR": ("tr",),
    "IRN": ("fa",),
    "AFG": ("fa",),
    "ISR": ("he", "en"),
    "LBN": ("ar", "fr"),
    "MAR": ("fr", "ar"),
    "TUN": ("fr", "ar"),
    "SEN": ("fr",),
    "CIV": ("fr",),
    "CMR": ("fr", "en"),
    "COD": ("fr",),
    "MDG": ("fr",),
    "TZA": ("en", "sw"),
    "CHN": ("zh-CN",),
    "TWN": ("zh-TW",),
    "MAC": ("zh-TW", "en"),
    "JPN": ("ja",),
    "KOR": ("ko",),
    "VNM": ("vi",),
    "THA": ("th",),
    "IDN": ("id",),
    "KHM": ("km", "en"),
}


def market_languages(market: str) -> list[str]:
    """Languages to offer for email to this market: the best one first, English always in."""
    found = list(MARKET_LANGUAGES.get(market.upper(), ("en",)))
    return found if "en" in found else [*found, "en"]


def language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code, code)
