// Amounts the way people type and read them ("18 lakh", "2.5 crore", "500k", "5 tons").

// South Asian currencies group digits in lakhs and crores (18,00,000).
const LAKH_CURRENCIES = new Set(["BDT", "INR", "LKR", "PKR"]);

const MULTIPLIERS: [RegExp, number][] = [
  [/^(k|thousand|hazar|hazaar)$/, 1e3],
  [/^(l|lac|lacs|lakh|lakhs)$/, 1e5],
  [/^(m|mn|million|millions)$/, 1e6],
  [/^(cr|crore|crores)$/, 1e7],
  [/^(b|bn|billion|billions|arab)$/, 1e9],
];

/** "18 lakh" -> 1_800_000, "1,250,000" -> 1_250_000, "2.5m" -> 2_500_000; null if unreadable. */
export function parseAmount(text: string): number | null {
  const match = text
    .trim()
    .toLowerCase()
    .replace(/[,\s_]/g, "")
    .match(/^(\d+(?:\.\d+)?)([a-z]*)$/);
  if (!match) return null;
  const [, digits, unit] = match;
  const scale = unit ? MULTIPLIERS.find(([pattern]) => pattern.test(unit))?.[1] : 1;
  return scale === undefined ? null : Number(digits) * scale;
}

const WEIGHTS: [RegExp, number][] = [
  [/^(|kg|kgs|kilo|kilos|kilogram|kilograms)$/, 1],
  [/^(t|mt|ton|tons|tonne|tonnes)$/, 1000],
];

/** "5 tons" -> 5000, "750kg" -> 750, "1200" -> 1200 (kg); null if unreadable. */
export function parseKg(text: string): number | null {
  const match = text
    .trim()
    .toLowerCase()
    .replace(/[,\s_]/g, "")
    .match(/^(\d+(?:\.\d+)?)([a-z]*)$/);
  if (!match) return null;
  const scale = WEIGHTS.find(([pattern]) => pattern.test(match[2]))?.[1];
  return scale === undefined ? null : Number(match[1]) * scale;
}

/** A local amount as people read it: "PKR 18,00,000 (18 lakh)" or "TRY 250,000". */
export function localMoney(value: number, currency: string): string {
  const lakhs = LAKH_CURRENCIES.has(currency);
  const text = new Intl.NumberFormat(lakhs ? "en-IN" : "en", {
    style: "currency",
    currency,
    currencyDisplay: "code",
    maximumFractionDigits: value < 100 ? 2 : 0,
  }).format(value);
  if (lakhs && value >= 1e7) return `${text} (${trim(value / 1e7)} crore)`;
  if (lakhs && value >= 1e5) return `${text} (${trim(value / 1e5)} lakh)`;
  return text;
}

const trim = (n: number) => String(Number(n.toFixed(2)));

/** Exact dollars for a converted amount: 6427.9 -> "$6,428"; small values keep cents. */
export function usd(value: number): string {
  return new Intl.NumberFormat("en", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: value < 100 ? 2 : 0,
  }).format(value);
}

export const perKg = (usdPerKg: number) => `$${usdPerKg.toFixed(2)}/kg`;

/** 2140 -> "2.1 t", 640 -> "640 kg". */
export function weight(kg: number): string {
  if (kg < 1000) return `${Math.round(kg)} kg`;
  const tonnes = kg / 1000;
  return `${tonnes < 10 ? trim(tonnes) : Math.round(tonnes).toLocaleString("en")} t`;
}
