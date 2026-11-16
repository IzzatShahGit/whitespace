"use client";

import { Coins, type LucideIcon, ShieldCheck, TrendingUp, Truck } from "lucide-react";

import { type Tone, toneClass } from "@/components/ui/badge";
import type { SourcingPick, SupplierOption } from "@/lib/api/queries";
import { signedPercent } from "@/lib/format";
import { perKg } from "@/lib/money";

type Kind = SourcingPick["kind"];

/** One look per pick, used by the cards, the product tiles and the table's tags. */
export const PICK: Record<Kind, { icon: LucideIcon; tone: Tone; short: string }> = {
  best_value: { icon: Coins, tone: "positive", short: "Best value" },
  most_established: { icon: ShieldCheck, tone: "brand", short: "Most established" },
  rising: { icon: TrendingUp, tone: "brand", short: "Rising" },
  // "You" is orange in Whitespace: this pick is about the user's own imports.
  current: { icon: Truck, tone: "accent", short: "Supplies you today" },
};

/** Tags from the API ("Lowest price", "Supplies you today", …) with a matching icon. */
export function tagLook(tag: string): { icon: LucideIcon; tone: Tone } {
  const t = tag.toLowerCase();
  if (t.includes("supplies you")) return PICK.current;
  if (t.includes("price") || t.includes("value")) return PICK.best_value;
  if (t.includes("grow") || t.includes("rising")) return PICK.rising;
  return PICK.most_established;
}

/** Scroll to a supplier's row (whichever layout is showing) and highlight it. */
export function showSupplier(code: string) {
  const rows = document.querySelectorAll<HTMLElement>(`[data-supplier="${code}"]`);
  const row = [...rows].find((el) => el.offsetParent !== null);
  if (!row) return;
  row.focus({ preventScroll: true });
  row.scrollIntoView({ behavior: "smooth", block: "center" });
}

export function PickCard({ pick, option }: { pick: SourcingPick; option?: SupplierOption }) {
  const { icon: Icon, tone } = PICK[pick.kind];
  const price = option?.unit_price_usd_kg;
  return (
    <a
      href="#compare"
      onClick={(e) => {
        e.preventDefault();
        showSupplier(pick.country.code);
      }}
      className="group flex h-full flex-col gap-3 rounded-2xl border border-line bg-surface p-4 shadow-card transition-colors duration-150 hover:border-line-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand sm:p-5"
    >
      <span className="flex items-center gap-2 text-sm font-medium text-muted">
        <span
          aria-hidden
          className={`flex h-8 w-8 items-center justify-center rounded-xl ${toneClass[tone]}`}
        >
          <Icon className="h-4 w-4" />
        </span>
        {pick.title}
      </span>
      <span>
        <span className="block text-xl font-semibold tracking-tight">{pick.country.name}</span>
        {option && pick.kind !== "current" && (
          <span className="mt-0.5 block text-sm text-muted tabular-nums">
            {price != null ? perKg(price) : "Price n/a"}
            {option.exports_growth_3y !== null &&
              ` · ${signedPercent(option.exports_growth_3y)}/yr`}
          </span>
        )}
      </span>
      <span className="text-sm leading-6 text-muted">{pick.reason}</span>
      <span className="mt-auto text-sm font-medium text-brand group-hover:underline">
        See in comparison
      </span>
    </a>
  );
}
