import { ArrowDownRight, ArrowUpRight, ChevronRight, Minus } from "lucide-react";
import Link from "next/link";

import { VerdictBadge } from "@/components/markets/verdict";
import { Badge } from "@/components/ui/badge";
import type { MarketItem } from "@/lib/api/queries";
import { money, percent, signedPercent } from "@/lib/format";

/** Columns shared by the list header and every row (phones: rank · market · figures). */
export const ROW_GRID =
  "grid grid-cols-[1.5rem_minmax(0,1fr)_auto] items-center gap-x-3 md:grid-cols-[2rem_minmax(0,1fr)_5rem_5rem_5rem_1rem]";

/** Growth with a small arrow, so the direction never relies on colour. */
export function Growth({ value, suffix = "" }: { value: number; suffix?: string }) {
  const rounded = Math.round(value * 100);
  const Icon = rounded > 0 ? ArrowUpRight : rounded < 0 ? ArrowDownRight : Minus;
  const tone = rounded > 0 ? "text-positive" : rounded < 0 ? "text-negative" : "text-subtle";
  return (
    <span className="inline-flex items-center justify-end gap-0.5 tabular-nums">
      <Icon aria-hidden className={`h-3.5 w-3.5 shrink-0 ${tone}`} strokeWidth={2.25} />
      {signedPercent(value)}
      {suffix}
    </span>
  );
}

/**
 * One ranked market as a table row: rank, name with its verdict, then imports, growth and
 * the exporter's share. The whole row opens the market.
 */
export function MarketRow({ item, href }: { item: MarketItem; href: string }) {
  const share = percent(item.exporter_share, { floor: true });
  return (
    <li>
      <Link
        href={href}
        aria-label={`#${item.rank} ${item.market.name}: ${item.verdict.headline}. Imports ${money(
          item.market_imports_usd,
        )}, growth ${signedPercent(item.import_growth_3y)} a year, your share ${share}${
          item.already_selling ? ". You sell here" : ""
        }`}
        className={`group ${ROW_GRID} px-4 py-3 transition-colors duration-150 hover:bg-surface-2/70 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand sm:px-5`}
      >
        <span className="self-start pt-0.5 text-sm text-subtle tabular-nums md:self-center md:pt-0">
          {item.rank}
        </span>
        <span className="min-w-0">
          <span className="flex min-w-0 items-center gap-2">
            <span className="truncate font-medium text-fg">{item.market.name}</span>
            {item.already_selling && (
              <span className="hidden shrink-0 sm:inline-flex">
                <Badge tone="neutral">You sell here</Badge>
              </span>
            )}
          </span>
          <span className="mt-1.5 flex">
            <VerdictBadge verdict={item.verdict} />
          </span>
        </span>

        {/* Phones: the three figures stacked on the right. */}
        <span className="text-right md:hidden">
          <span className="block text-sm font-medium tabular-nums">
            {money(item.market_imports_usd)}
          </span>
          <span className="mt-1 flex items-center justify-end gap-1 text-xs text-muted">
            <Growth value={item.import_growth_3y} suffix="/yr" />
            <span aria-hidden>·</span>
            <span className="tabular-nums">{share}</span>
          </span>
        </span>

        <span className="hidden text-right text-sm font-medium tabular-nums md:block">
          {money(item.market_imports_usd)}
        </span>
        <span className="hidden justify-end text-sm md:flex">
          <Growth value={item.import_growth_3y} />
        </span>
        <span className="hidden text-right text-sm tabular-nums md:block">{share}</span>
        <ChevronRight
          aria-hidden
          className="hidden h-4 w-4 text-subtle transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-fg md:block"
        />
      </Link>
    </li>
  );
}

export function MarketRowSkeleton() {
  return (
    <li aria-hidden className={`${ROW_GRID} px-4 py-3.5 sm:px-5`}>
      <span className="skeleton h-4 w-4" />
      <span className="flex flex-col gap-2">
        <span className="skeleton h-4 w-32" />
        <span className="skeleton h-5 w-24 rounded-full" />
      </span>
      <span className="skeleton h-8 w-20 md:hidden" />
      <span className="skeleton hidden h-4 w-14 justify-self-end md:block" />
      <span className="skeleton hidden h-4 w-12 justify-self-end md:block" />
      <span className="skeleton hidden h-4 w-10 justify-self-end md:block" />
      <span className="hidden md:block" />
    </li>
  );
}
