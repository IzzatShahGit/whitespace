"""Product niches: plain-language groups of HS codes for browsing.

Each niche lists HS code prefixes (2, 4 or 6 digits): "6115" covers every sock and
hosiery product, "39" all of chapter 39 (plastics). Names are our own wording, chosen
for what exporters in the covered countries actually sell.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Niche:
    slug: str
    name: str
    sector: str
    prefixes: tuple[str, ...]

    def matches(self, hs6: str) -> bool:
        return hs6.startswith(self.prefixes)


TEXTILES = "Textiles & apparel"
FOOD = "Food & agriculture"
MATERIALS = "Materials & chemicals"
INDUSTRIAL = "Manufactured goods"

NICHES: tuple[Niche, ...] = (
    # Textiles & apparel
    Niche("cotton-yarn", "Cotton yarn", TEXTILES, ("5205", "5206", "5207")),
    Niche(
        "woven-fabrics",
        "Woven fabrics",
        TEXTILES,
        (
            "5208",
            "5209",
            "5210",
            "5211",
            "5212",
            "5407",
            "5408",
            "5512",
            "5513",
            "5514",
            "5515",
            "5516",
        ),
    ),
    Niche("knitted-fabrics", "Knitted fabrics", TEXTILES, ("60",)),
    Niche("t-shirts", "T-shirts & tops", TEXTILES, ("6109",)),
    Niche("knitwear", "Sweaters & knitwear", TEXTILES, ("6110",)),
    Niche(
        "trousers-jeans",
        "Trousers & jeans",
        TEXTILES,
        ("620342", "620343", "620462", "620463", "610342", "610462"),
    ),
    Niche("shirts", "Shirts & blouses", TEXTILES, ("6105", "6106", "6205", "6206")),
    Niche("socks", "Socks & hosiery", TEXTILES, ("6115",)),
    Niche("babywear", "Babies' garments", TEXTILES, ("6111", "6209")),
    Niche("sportswear", "Sportswear & tracksuits", TEXTILES, ("6112", "6211")),
    Niche("home-textiles", "Bed, bath & kitchen linen", TEXTILES, ("6302",)),
    Niche("towels", "Towels", TEXTILES, ("630260", "630291", "630293", "630299")),
    Niche("carpets", "Carpets & rugs", TEXTILES, ("57",)),
    Niche("leather-apparel", "Leather garments & gloves", TEXTILES, ("4203",)),
    Niche("leather-goods", "Bags & leather goods", TEXTILES, ("4202",)),
    Niche("footwear", "Footwear", TEXTILES, ("64",)),
    # Food & agriculture
    Niche("rice", "Rice", FOOD, ("1006",)),
    Niche("tropical-fruit", "Mangoes, dates & tropical fruit", FOOD, ("0803", "0804")),
    Niche("citrus", "Citrus fruit", FOOD, ("0805",)),
    Niche(
        "fresh-vegetables",
        "Fresh vegetables",
        FOOD,
        ("0701", "0702", "0703", "0704", "0705", "0706", "0707", "0708", "0709"),
    ),
    Niche("nuts", "Nuts", FOOD, ("0801", "0802")),
    Niche("tea-coffee", "Tea & coffee", FOOD, ("0901", "0902")),
    Niche("spices", "Spices", FOOD, ("0904", "0905", "0906", "0907", "0908", "0909", "0910")),
    Niche("fish-seafood", "Fish & seafood", FOOD, ("03", "1604", "1605")),
    Niche("meat", "Meat", FOOD, ("02",)),
    Niche("dairy", "Dairy & eggs", FOOD, ("04",)),
    Niche("flowers", "Cut flowers & plants", FOOD, ("06",)),
    Niche("sugar-confectionery", "Sugar & confectionery", FOOD, ("17",)),
    Niche("bakery-snacks", "Bakery & snacks", FOOD, ("1904", "1905", "2005", "2008")),
    Niche("vegetable-oils", "Vegetable oils", FOOD, ("15",)),
    # Materials & chemicals
    Niche(
        "plastic-raw",
        "Plastic raw materials",
        MATERIALS,
        (
            "3901",
            "3902",
            "3903",
            "3904",
            "3905",
            "3906",
            "3907",
            "3908",
            "3909",
            "3910",
            "3911",
            "3912",
            "3913",
            "3914",
        ),
    ),
    Niche(
        "plastic-products",
        "Plastic products & packaging",
        MATERIALS,
        ("3916", "3917", "3918", "3919", "3920", "3921", "3922", "3923", "3924", "3925", "3926"),
    ),
    Niche("rubber", "Rubber & tyres", MATERIALS, ("40",)),
    Niche("paper-packaging", "Paper & packaging", MATERIALS, ("48",)),
    Niche("chemicals", "Industrial chemicals", MATERIALS, ("28", "29")),
    Niche("pharma", "Pharmaceuticals", MATERIALS, ("30",)),
    Niche(
        "cosmetics",
        "Cosmetics & personal care",
        MATERIALS,
        ("3303", "3304", "3305", "3306", "3307", "3401"),
    ),
    Niche("cement-stone", "Cement, stone & marble", MATERIALS, ("2523", "6802")),
    Niche("ceramics-glass", "Ceramics & glassware", MATERIALS, ("69", "70")),
    Niche("steel", "Iron & steel products", MATERIALS, ("72", "73")),
    Niche("aluminium-copper", "Aluminium & copper", MATERIALS, ("74", "76")),
    # Manufactured goods
    Niche(
        "surgical", "Surgical & medical instruments", INDUSTRIAL, ("9018", "9019", "9020", "9021")
    ),
    Niche("sports-goods", "Sports goods & balls", INDUSTRIAL, ("9506",)),
    Niche("toys", "Toys & games", INDUSTRIAL, ("9503", "9504")),
    Niche("furniture", "Furniture", INDUSTRIAL, ("9401", "9403")),
    Niche(
        "cutlery-tools",
        "Cutlery & hand tools",
        INDUSTRIAL,
        ("8201", "8202", "8203", "8204", "8205", "8211", "8214", "8215"),
    ),
    Niche("electrical", "Cables & electrical parts", INDUSTRIAL, ("8536", "8544")),
    Niche("auto-parts", "Vehicle parts", INDUSTRIAL, ("8708",)),
    Niche("jewellery", "Jewellery", INDUSTRIAL, ("7113", "7117")),
)

SECTORS: tuple[str, ...] = (TEXTILES, FOOD, MATERIALS, INDUSTRIAL)
BY_SLUG: dict[str, Niche] = {n.slug: n for n in NICHES}
