// Display formatting for numbers that come from the API.

/** Compact amount in a currency: 2_040_000 -> "$2.0M", or "€2.0M" for EUR. */
export function amount(value: number, currency: string): string {
  const text = money(value);
  return currency === "EUR" ? text.replace("$", "€") : text;
}

/** "2026-08" -> "Aug 2026" (or "Aug 26" when short). */
export function monthLabel(month: string, short = false): string {
  const [year, m] = month.split("-").map(Number);
  const name = new Date(Date.UTC(year, m - 1, 1)).toLocaleString("en", {
    month: "short",
    timeZone: "UTC",
  });
  return `${name} ${short ? String(year).slice(2) : year}`;
}

export function money(usd: number): string {
  for (const [unit, size] of [
    ["B", 1e9],
    ["M", 1e6],
    ["K", 1e3],
  ] as const) {
    if (usd >= size) {
      const amount = usd / size;
      return `$${amount < 10 ? amount.toFixed(1) : amount.toFixed(0)}${unit}`;
    }
  }
  return `$${usd.toFixed(0)}`;
}

/** 0.153 -> "15%"; shares under 1% read "<1%" rather than a misleading "0%". */
export function percent(value: number, { floor = false } = {}): string {
  if (floor && value > 0 && value < 0.01) return "<1%";
  return `${Math.round(value * 100)}%`;
}

/** Signed growth: 0.19 -> "+19%", -0.03 -> "−3%". */
export function signedPercent(value: number): string {
  const rounded = Math.round(value * 100);
  if (rounded === 0) return "0%";
  return `${rounded > 0 ? "+" : "−"}${Math.abs(rounded)}%`;
}

/** Share change in percentage points: -0.09 -> "−9 pts". */
export function points(value: number): string {
  const rounded = Math.round(value * 100);
  if (rounded === 0) return "±0 pts";
  return `${rounded > 0 ? "+" : "−"}${Math.abs(rounded)} pts`;
}

/**
 * A readable product name from a BACI description, which comes in two shapes:
 * - "Bed linen: of cotton (…)": the head is the product, so join head and detail
 *   -> "Bed linen of cotton (…)".
 * - "Cereals: rice, broken": the head is only a category -> "Rice, broken".
 */
export function shortProductName(description: string): string {
  const [head, ...rest] = description.split(": ");
  if (!rest.length) return head;
  const detail = rest.join(": ");
  const continuesHead = /^(of|from|for|in|with|without|not)\b/.test(detail);
  const name = continuesHead ? `${head} ${detail}` : detail;
  return name.charAt(0).toUpperCase() + name.slice(1);
}
