"""Amazon US top-level categories, and which customs codes sell in them.

One table serves three jobs:
- the weekly best-seller lists (each category's public best-seller page),
- hot categories from US import statistics (customs codes grouped by category),
- the FBA calculator's fee category for a customs code.

The code lists are deliberately narrow: consumer goods a small seller can import and
send to Amazon, by HS heading (4 digits) or subheading (6 digits). A code in no list
isn't counted anywhere, so "hot categories" never mixes in industrial trade.
"""

from __future__ import annotations

from dataclasses import dataclass

BESTSELLERS_URL = "https://www.amazon.com/gp/bestsellers/{slug}"


@dataclass(frozen=True)
class AmazonCategory:
    key: str
    label: str
    slug: str  # Amazon's best-seller path: amazon.com/gp/bestsellers/<slug>
    codes: tuple[str, ...] = ()  # HS headings or subheadings in this category
    fee: str = "other"  # fee category in the FBA calculator (services/fba_fees.py)

    @property
    def bestsellers_url(self) -> str:
        return BESTSELLERS_URL.format(slug=self.slug)


CATEGORIES: tuple[AmazonCategory, ...] = (
    AmazonCategory(
        "home", "Home & Kitchen", "home-garden",
        ("3406", "392490", "4414", "4602", "6302", "6303", "6304", "6307", "6702", "6913",
         "7009", "9404", "9405", "9603"),
        "home_kitchen",
    ),
    AmazonCategory(
        "kitchen", "Kitchen & Dining", "kitchen",
        ("392410", "4419", "6911", "6912", "7013", "7323", "7615", "8211", "8215",
         "850940", "851660", "851671", "851672", "851679", "9617"),
        "home_kitchen",
    ),
    AmazonCategory(
        "beauty", "Beauty & Personal Care", "beauty",
        ("3303", "3304", "3305", "3306", "3307", "3401", "6704", "8510", "851631",
         "851632", "851633", "9615", "9616"),
        "beauty_health",
    ),
    AmazonCategory(
        "health", "Health & Household", "hpc", ("3005", "9019", "9619"), "beauty_health"
    ),
    AmazonCategory("baby", "Baby", "baby-products", ("6111", "6209", "8715"), "baby"),
    AmazonCategory(
        "fashion", "Clothing, Shoes & Jewelry", "fashion",
        ("61", "62", "64", "65", "4202", "4203", "6601", "7113", "7117", "9004", "9101",
         "9102"),
        "clothing",
    ),
    AmazonCategory(
        "sports", "Sports & Outdoors", "sporting-goods", ("6306", "9506", "9507"), "sports"
    ),
    AmazonCategory("toys", "Toys & Games", "toys-and-games", ("9503", "9504", "9505"), "toys"),
    AmazonCategory("pet", "Pet Supplies", "pet-supplies", ("4201", "230910"), "pet"),
    AmazonCategory(
        "office", "Office Products", "office-products",
        ("4817", "4820", "8304", "8305", "9608", "9609", "9610"),
    ),
    AmazonCategory(
        "tools", "Tools & Home Improvement", "hi",
        ("8201", "8202", "8203", "8204", "8205", "8301", "8302", "8467"),
    ),
    AmazonCategory("automotive", "Automotive", "automotive", ("8512",)),
    AmazonCategory(
        "electronics", "Electronics", "electronics",
        ("847160", "850440", "850760", "8518", "8519", "852589", "8527",
         "854442"),
        "electronics_accessories",
    ),
    AmazonCategory(
        "phones", "Cell Phones & Accessories", "wireless", (), "electronics_accessories"
    ),
    AmazonCategory(
        "crafts", "Arts, Crafts & Sewing", "arts-crafts",
        ("3213", "5204", "5508", "5806", "5808", "5810"),
    ),
)  # fmt: skip

BY_KEY: dict[str, AmazonCategory] = {c.key: c for c in CATEGORIES}

# Fee categories that differ from the code's Amazon category (checked first).
_FEE_OVERRIDES: tuple[tuple[str, str], ...] = (
    ("64", "footwear"),
    ("4202", "luggage"),
    ("7113", "jewelry"),
    ("7117", "jewelry"),
    ("9101", "other"),  # watches
    ("9102", "other"),
    ("6111", "clothing"),  # babies' clothes are priced as clothing
    ("6209", "clothing"),
    ("8518", "consumer_electronics"),
    ("8519", "consumer_electronics"),
    ("852589", "consumer_electronics"),
    ("8527", "consumer_electronics"),
)


def _matches(hs6: str, codes: tuple[str, ...]) -> bool:
    return any(hs6.startswith(code) for code in codes)


def category_of(hs6: str) -> AmazonCategory | None:
    """The Amazon category a customs code sells in, or None if we don't map it."""
    for category in CATEGORIES:
        if _matches(hs6, category.codes):
            return category
    return None


def fee_category(hs6: str) -> str:
    """The FBA calculator's fee category for a code ("other" when unknown)."""
    for code, fee in _FEE_OVERRIDES:
        if hs6.startswith(code):
            return fee
    found = category_of(hs6)
    return found.fee if found else "other"
