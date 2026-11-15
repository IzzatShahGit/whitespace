// Which currency each country prices in, and the currencies to offer first.

// Grouped by currency so shared currencies (euro, CFA franc, …) stay readable.
// prettier-ignore
const COUNTRIES_BY_CURRENCY: Record<string, string[]> = {
  EUR: [
    "AND", "AUT", "BEL", "CYP", "DEU", "ESP", "EST", "FIN", "FRA", "GRC", "HRV", "IRL", "ITA",
    "LTU", "LUX", "LVA", "MCO", "MLT", "MNE", "NLD", "PRT", "SMR", "SVK", "SVN", "VAT",
  ],
  USD: [
    "ASM", "ECU", "FSM", "GUM", "MHL", "MNP", "PLW", "PRI", "SLV", "TCA", "TLS", "USA", "VGB",
    "VIR", "ZWE",
  ],
  XOF: ["BEN", "BFA", "CIV", "GNB", "MLI", "NER", "SEN", "TGO"],
  XAF: ["CAF", "CMR", "COG", "GAB", "GNQ", "TCD"],
  XCD: ["AIA", "ATG", "DMA", "GRD", "KNA", "LCA", "MSR", "VCT"],
  AUD: ["AUS", "CXR", "KIR", "NFK", "NRU", "TUV"],
  NZD: ["COK", "NIU", "NZL", "TKL"],
  DKK: ["DNK", "FRO", "GRL"],
  CHF: ["CHE", "LIE"],
  NOK: ["NOR", "SJM"],
  GBP: ["GBR", "GGY", "IMN", "JEY"],
  ANG: ["CUW", "SXM"],
  XPF: ["NCL", "PYF", "WLF"],
  INR: ["IND"],
  ZAR: ["ZAF"],
};

// prettier-ignore
const SINGLE: Record<string, string> = {
  AFG: "AFN", AGO: "AOA", ALB: "ALL", ARE: "AED", ARG: "ARS", ARM: "AMD", AZE: "AZN",
  BDI: "BIF", BGD: "BDT", BGR: "BGN", BHR: "BHD", BHS: "BSD", BIH: "BAM", BLR: "BYN",
  BLZ: "BZD", BMU: "BMD", BOL: "BOB", BRA: "BRL", BRB: "BBD", BRN: "BND", BTN: "BTN",
  BWA: "BWP", CAN: "CAD", CHL: "CLP", CHN: "CNY", COD: "CDF", COL: "COP", COM: "KMF",
  CPV: "CVE", CRI: "CRC", CUB: "CUP", CYM: "KYD", CZE: "CZK", DJI: "DJF", DOM: "DOP",
  DZA: "DZD", EGY: "EGP", ERI: "ERN", ETH: "ETB", FJI: "FJD", GEO: "GEL", GHA: "GHS",
  GIN: "GNF", GMB: "GMD", GTM: "GTQ", GUY: "GYD", HKG: "HKD", HND: "HNL", HTI: "HTG",
  HUN: "HUF", IDN: "IDR", IRN: "IRR", IRQ: "IQD", ISL: "ISK", ISR: "ILS", JAM: "JMD",
  JOR: "JOD", JPN: "JPY", KAZ: "KZT", KEN: "KES", KGZ: "KGS", KHM: "KHR", KOR: "KRW",
  KWT: "KWD", LAO: "LAK", LBN: "LBP", LBR: "LRD", LBY: "LYD", LKA: "LKR", LSO: "LSL",
  MAC: "MOP", MAR: "MAD", MDA: "MDL", MDG: "MGA", MDV: "MVR", MEX: "MXN", MKD: "MKD",
  MMR: "MMK", MNG: "MNT", MOZ: "MZN", MRT: "MRU", MUS: "MUR", MWI: "MWK", MYS: "MYR",
  NAM: "NAD", NGA: "NGN", NIC: "NIO", NPL: "NPR", OMN: "OMR", PAK: "PKR", PAN: "PAB",
  PER: "PEN", PHL: "PHP", PNG: "PGK", POL: "PLN", PRK: "KPW", PRY: "PYG", PSE: "ILS",
  QAT: "QAR", ROU: "RON", RUS: "RUB", RWA: "RWF", SAU: "SAR", SDN: "SDG", SGP: "SGD",
  SLB: "SBD", SLE: "SLE", SOM: "SOS", SRB: "RSD", SSD: "SSP", STP: "STN", SUR: "SRD",
  SWE: "SEK", SWZ: "SZL", SYC: "SCR", SYR: "SYP", TJK: "TJS", TKM: "TMT", THA: "THB",
  TON: "TOP", TTO: "TTD", TUN: "TND", TUR: "TRY", TWN: "TWD", TZA: "TZS", UGA: "UGX",
  UKR: "UAH", URY: "UYU", UZB: "UZS", VEN: "VES", VNM: "VND", VUT: "VUV", WSM: "WST",
  YEM: "YER", ZMB: "ZMW",
};

const BY_COUNTRY: Record<string, string> = {
  ...SINGLE,
  ...Object.fromEntries(
    Object.entries(COUNTRIES_BY_CURRENCY).flatMap(([currency, countries]) =>
      countries.map((country) => [country, currency]),
    ),
  ),
};

/** The currency a country prices in; dollars when unknown. */
export function currencyOf(country: string | undefined): string {
  return (country && BY_COUNTRY[country]) || "USD";
}

/** What exporters and importers trade in most, offered after the user's own currencies. */
export const TRADE_CURRENCIES = ["USD", "EUR", "GBP", "CNY", "AED", "SAR", "JPY"];

/** The currencies to offer first: the given ones (own, market's) then the main trade ones. */
export function suggestedCurrencies(...first: (string | undefined)[]): string[] {
  return [...new Set([...first.filter((c): c is string => Boolean(c)), ...TRADE_CURRENCIES])];
}

const names = new Intl.DisplayNames(["en"], { type: "currency" });

/** "PKR" -> "Pakistani Rupee" (the code itself if the browser doesn't know it). */
export function currencyName(code: string): string {
  try {
    return names.of(code) ?? code;
  } catch {
    return code;
  }
}
