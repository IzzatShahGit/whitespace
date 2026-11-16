"""Country code tables, keyed by ISO 3166-1 alpha-3 (the codes in our country table).

`ISO_NUMERIC` maps to ISO 3166-1 numeric codes, which are also the UN M49 codes that
WITS tariff data and world-map geometries use, as zero-padded strings ("004").
`ISO_ALPHA2` maps to two-letter codes (the UK Trade Tariff uses them).

Generated once from CEPII BACI's country list (country_codes_V202601.csv: numeric
code, ISO alpha-2, ISO alpha-3), with three corrections:
- UN Comtrade, and so BACI, gives five countries numeric codes of its own; the ISO
  codes are used here, and Comtrade's are kept in `COMTRADE_NUMERIC` because some
  WITS tariff reporters (Canada, for one) still list partners under them.
- Historic entries ("Fed. Rep. of Germany (...1990)") are dropped.
- BACI groupings with no ISO code (S19 "Other Asia, nes", R20, ZA1, PUS) are left out.
"""

from __future__ import annotations

ISO_NUMERIC: dict[str, str] = {
    "ABW": "533", "AFG": "004", "AGO": "024", "AIA": "660", "ALB": "008", "AND": "020",
    "ARE": "784", "ARG": "032", "ARM": "051", "ASM": "016", "ATF": "260", "ATG": "028",
    "AUS": "036", "AUT": "040", "AZE": "031", "BDI": "108", "BEL": "056", "BEN": "204",
    "BES": "535", "BFA": "854", "BGD": "050", "BGR": "100", "BHR": "048", "BHS": "044",
    "BIH": "070", "BLM": "652", "BLR": "112", "BLZ": "084", "BMU": "060", "BOL": "068",
    "BRA": "076", "BRB": "052", "BRN": "096", "BTN": "064", "BWA": "072", "CAF": "140",
    "CAN": "124", "CCK": "166", "CHE": "756", "CHL": "152", "CHN": "156", "CIV": "384",
    "CMR": "120", "COD": "180", "COG": "178", "COK": "184", "COL": "170", "COM": "174",
    "CPV": "132", "CRI": "188", "CUB": "192", "CUW": "531", "CXR": "162", "CYM": "136",
    "CYP": "196", "CZE": "203", "DEU": "276", "DJI": "262", "DMA": "212", "DNK": "208",
    "DOM": "214", "DZA": "012", "ECU": "218", "EGY": "818", "ERI": "232", "ESP": "724",
    "EST": "233", "ETH": "231", "FIN": "246", "FJI": "242", "FLK": "238", "FRA": "250",
    "FSM": "583", "GAB": "266", "GBR": "826", "GEO": "268", "GHA": "288", "GIB": "292",
    "GIN": "324", "GMB": "270", "GNB": "624", "GNQ": "226", "GRC": "300", "GRD": "308",
    "GRL": "304", "GTM": "320", "GUM": "316", "GUY": "328", "HKG": "344", "HND": "340",
    "HRV": "191", "HTI": "332", "HUN": "348", "IDN": "360", "IND": "356", "IOT": "086",
    "IRL": "372", "IRN": "364", "IRQ": "368", "ISL": "352", "ISR": "376", "ITA": "380",
    "JAM": "388", "JOR": "400", "JPN": "392", "KAZ": "398", "KEN": "404", "KGZ": "417",
    "KHM": "116", "KIR": "296", "KNA": "659", "KOR": "410", "KWT": "414", "LAO": "418",
    "LBN": "422", "LBR": "430", "LBY": "434", "LCA": "662", "LKA": "144", "LSO": "426",
    "LTU": "440", "LUX": "442", "LVA": "428", "MAC": "446", "MAR": "504", "MDA": "498",
    "MDG": "450", "MDV": "462", "MEX": "484", "MHL": "584", "MKD": "807", "MLI": "466",
    "MLT": "470", "MMR": "104", "MNE": "499", "MNG": "496", "MNP": "580", "MOZ": "508",
    "MRT": "478", "MSR": "500", "MUS": "480", "MWI": "454", "MYS": "458", "MYT": "175",
    "NAM": "516", "NCL": "540", "NER": "562", "NFK": "574", "NGA": "566", "NIC": "558",
    "NIU": "570", "NLD": "528", "NOR": "578", "NPL": "524", "NRU": "520", "NZL": "554",
    "OMN": "512", "PAK": "586", "PAN": "591", "PCN": "612", "PER": "604", "PHL": "608",
    "PLW": "585", "PNG": "598", "POL": "616", "PRK": "408", "PRT": "620", "PRY": "600",
    "PSE": "275", "PYF": "258", "QAT": "634", "ROU": "642", "RUS": "643", "RWA": "646",
    "SAU": "682", "SDN": "729", "SEN": "686", "SGP": "702", "SHN": "654", "SLB": "090",
    "SLE": "694", "SLV": "222", "SMR": "674", "SOM": "706", "SPM": "666", "SRB": "688",
    "SSD": "728", "STP": "678", "SUR": "740", "SVK": "703", "SVN": "705", "SWE": "752",
    "SWZ": "748", "SXM": "534", "SYC": "690", "SYR": "760", "TCA": "796", "TCD": "148",
    "TGO": "768", "THA": "764", "TJK": "762", "TKL": "772", "TKM": "795", "TLS": "626",
    "TON": "776", "TTO": "780", "TUN": "788", "TUR": "792", "TUV": "798", "TZA": "834",
    "UGA": "800", "UKR": "804", "URY": "858", "USA": "840", "UZB": "860", "VCT": "670",
    "VEN": "862", "VGB": "092", "VNM": "704", "VUT": "548", "WLF": "876", "WSM": "882",
    "YEM": "887", "ZAF": "710", "ZMB": "894", "ZWE": "716",
}  # fmt: skip

# UN Comtrade's own numeric codes, where they differ from ISO.
COMTRADE_NUMERIC: dict[str, str] = {
    "CHE": "757", "FRA": "251", "IND": "699", "NOR": "579", "USA": "842",
}  # fmt: skip

ISO_ALPHA2: dict[str, str] = {
    "ABW": "AW", "AFG": "AF", "AGO": "AO", "AIA": "AI", "ALB": "AL", "AND": "AD",
    "ARE": "AE", "ARG": "AR", "ARM": "AM", "ASM": "AS", "ATF": "TF", "ATG": "AG",
    "AUS": "AU", "AUT": "AT", "AZE": "AZ", "BDI": "BI", "BEL": "BE", "BEN": "BJ",
    "BES": "BQ", "BFA": "BF", "BGD": "BD", "BGR": "BG", "BHR": "BH", "BHS": "BS",
    "BIH": "BA", "BLM": "BL", "BLR": "BY", "BLZ": "BZ", "BMU": "BM", "BOL": "BO",
    "BRA": "BR", "BRB": "BB", "BRN": "BN", "BTN": "BT", "BWA": "BW", "CAF": "CF",
    "CAN": "CA", "CCK": "CC", "CHE": "CH", "CHL": "CL", "CHN": "CN", "CIV": "CI",
    "CMR": "CM", "COD": "CD", "COG": "CG", "COK": "CK", "COL": "CO", "COM": "KM",
    "CPV": "CV", "CRI": "CR", "CUB": "CU", "CUW": "CW", "CXR": "CX", "CYM": "KY",
    "CYP": "CY", "CZE": "CZ", "DEU": "DE", "DJI": "DJ", "DMA": "DM", "DNK": "DK",
    "DOM": "DO", "DZA": "DZ", "ECU": "EC", "EGY": "EG", "ERI": "ER", "ESP": "ES",
    "EST": "EE", "ETH": "ET", "FIN": "FI", "FJI": "FJ", "FLK": "FK", "FRA": "FR",
    "FSM": "FM", "GAB": "GA", "GBR": "GB", "GEO": "GE", "GHA": "GH", "GIB": "GI",
    "GIN": "GN", "GMB": "GM", "GNB": "GW", "GNQ": "GQ", "GRC": "GR", "GRD": "GD",
    "GRL": "GL", "GTM": "GT", "GUM": "GU", "GUY": "GY", "HKG": "HK", "HND": "HN",
    "HRV": "HR", "HTI": "HT", "HUN": "HU", "IDN": "ID", "IND": "IN", "IOT": "IO",
    "IRL": "IE", "IRN": "IR", "IRQ": "IQ", "ISL": "IS", "ISR": "IL", "ITA": "IT",
    "JAM": "JM", "JOR": "JO", "JPN": "JP", "KAZ": "KZ", "KEN": "KE", "KGZ": "KG",
    "KHM": "KH", "KIR": "KI", "KNA": "KN", "KOR": "KR", "KWT": "KW", "LAO": "LA",
    "LBN": "LB", "LBR": "LR", "LBY": "LY", "LCA": "LC", "LKA": "LK", "LSO": "LS",
    "LTU": "LT", "LUX": "LU", "LVA": "LV", "MAC": "MO", "MAR": "MA", "MDA": "MD",
    "MDG": "MG", "MDV": "MV", "MEX": "MX", "MHL": "MH", "MKD": "MK", "MLI": "ML",
    "MLT": "MT", "MMR": "MM", "MNE": "ME", "MNG": "MN", "MNP": "MP", "MOZ": "MZ",
    "MRT": "MR", "MSR": "MS", "MUS": "MU", "MWI": "MW", "MYS": "MY", "MYT": "YT",
    "NAM": "NA", "NCL": "NC", "NER": "NE", "NFK": "NF", "NGA": "NG", "NIC": "NI",
    "NIU": "NU", "NLD": "NL", "NOR": "NO", "NPL": "NP", "NRU": "NR", "NZL": "NZ",
    "OMN": "OM", "PAK": "PK", "PAN": "PA", "PCN": "PN", "PER": "PE", "PHL": "PH",
    "PLW": "PW", "PNG": "PG", "POL": "PL", "PRK": "KP", "PRT": "PT", "PRY": "PY",
    "PSE": "PS", "PYF": "PF", "QAT": "QA", "ROU": "RO", "RUS": "RU", "RWA": "RW",
    "SAU": "SA", "SDN": "SD", "SEN": "SN", "SGP": "SG", "SHN": "SH", "SLB": "SB",
    "SLE": "SL", "SLV": "SV", "SMR": "SM", "SOM": "SO", "SPM": "PM", "SRB": "RS",
    "SSD": "SS", "STP": "ST", "SUR": "SR", "SVK": "SK", "SVN": "SI", "SWE": "SE",
    "SWZ": "SZ", "SXM": "SX", "SYC": "SC", "SYR": "SY", "TCA": "TC", "TCD": "TD",
    "TGO": "TG", "THA": "TH", "TJK": "TJ", "TKL": "TK", "TKM": "TM", "TLS": "TL",
    "TON": "TO", "TTO": "TT", "TUN": "TN", "TUR": "TR", "TUV": "TV", "TZA": "TZ",
    "UGA": "UG", "UKR": "UA", "URY": "UY", "USA": "US", "UZB": "UZ", "VCT": "VC",
    "VEN": "VE", "VGB": "VG", "VNM": "VN", "VUT": "VU", "WLF": "WF", "WSM": "WS",
    "YEM": "YE", "ZAF": "ZA", "ZMB": "ZM", "ZWE": "ZW",
}  # fmt: skip
