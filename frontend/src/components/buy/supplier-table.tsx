"use client";

import { ArrowDown, ArrowUp } from "lucide-react";
import { useState } from "react";

import { tagLook } from "@/components/buy/picks";
import { Badge } from "@/components/ui/badge";
import { InfoTip } from "@/components/ui/info-tip";
import { Segmented } from "@/components/ui/segmented";
import type { SupplierOption } from "@/lib/api/queries";
import { percent, signedPercent } from "@/lib/format";
import { perKg, weight } from "@/lib/money";

type Sort = "price" | "growth" | "reach" | "size";

const SORTS: { value: Sort; label: string }[] = [
  { value: "price", label: "Cheapest" },
  { value: "growth", label: "Fastest growing" },
  { value: "reach", label: "Most markets" },
  { value: "size", label: "Biggest" },
];

const missingLast = (v: number | null, dir: 1 | -1) => (v === null ? Infinity : v * dir);

function sorted(rows: SupplierOption[], sort: Sort): SupplierOption[] {
  const by: Record<Sort, (s: SupplierOption) => number> = {
    price: (s) => missingLast(s.unit_price_usd_kg, 1),
    growth: (s) => missingLast(s.exports_growth_3y, -1),
    reach: (s) => -s.markets_served,
    size: (s) => -s.exports_usd,
  };
  return [...rows].sort((a, b) => by[sort](a) - by[sort](b));
}

/** Growth is a momentum signal: ±5% a year or more counts as moving (as the API's signals do). */
function growthClass(g: number | null) {
  if (g === null) return "text-subtle";
  return g >= 0.05 ? "text-positive" : g <= -0.05 ? "text-negative" : "text-muted";
}

function vsMedian(price: number, median: number | null): string | undefined {
  if (!median) return undefined;
  const diff = price / median - 1;
  if (Math.abs(diff) < 0.03) return "About the median";
  return `${Math.round(Math.abs(diff) * 100)}% ${diff < 0 ? "below" : "above"} median`;
}

function PriceBar({ price, median, max }: { price: number; median: number | null; max: number }) {
  return (
    <span aria-hidden className="relative block h-1.5 w-full rounded-full bg-surface-2">
      <span
        className="absolute inset-y-0 left-0 rounded-full"
        style={{ width: `${(price / max) * 100}%`, background: "var(--chart-end)" }}
      />
      {median && (
        <span
          className="absolute -inset-y-1 w-0 border-l-2 border-dotted border-fg/50"
          style={{ left: `${(median / max) * 100}%` }}
        />
      )}
    </span>
  );
}

function Tags({ tags }: { tags: string[] }) {
  if (tags.length === 0) return null;
  return (
    <span className="flex flex-wrap gap-1">
      {tags.map((tag) => {
        const { icon: Icon, tone } = tagLook(tag);
        return (
          <Badge key={tag} tone={tone} icon={<Icon aria-hidden />}>
            {tag}
          </Badge>
        );
      })}
    </span>
  );
}

const rowFocus = "scroll-mt-28 outline-none focus:bg-brand-soft transition-colors duration-500";

/**
 * Every supplier side by side: price per kg against the median, momentum, reach, size,
 * and what the user's budget buys. A table on wide screens, a list on phones.
 */
export function SupplierTable({
  suppliers,
  median,
  budgetUsd,
}: {
  suppliers: SupplierOption[];
  median: number | null;
  budgetUsd?: number;
}) {
  const [sort, setSort] = useState<Sort>("price");
  const rows = sorted(suppliers, sort);
  const max = Math.max(...suppliers.map((s) => s.unit_price_usd_kg ?? 0), median ?? 0) * 1.05 || 1;
  const buys = (s: SupplierOption) =>
    budgetUsd && s.unit_price_usd_kg ? `≈ ${weight(budgetUsd / s.unit_price_usd_kg)}` : "–";

  const head = "px-3 py-2.5 text-xs font-medium whitespace-nowrap text-muted";
  const arrow = (key: Sort) =>
    sort === key ? (
      key === "price" ? (
        <ArrowUp aria-hidden className="h-3.5 w-3.5" />
      ) : (
        <ArrowDown aria-hidden className="h-3.5 w-3.5" />
      )
    ) : null;
  const ariaSort = (key: Sort) =>
    sort === key ? (key === "price" ? "ascending" : "descending") : undefined;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 sm:px-5">
        <span className="text-sm text-muted">Sort by</span>
        <Segmented label="Sort suppliers" items={SORTS} value={sort} onChange={setSort} />
      </div>

      {/* Wide screens: a real table. */}
      <table className="hidden w-full border-collapse text-sm md:table">
        <caption className="sr-only">Supplier countries compared</caption>
        <thead>
          <tr className="border-y border-line bg-surface-2/60 text-left">
            <th scope="col" className={`${head} pl-5`}>
              Supplier
            </th>
            <th scope="col" aria-sort={ariaSort("price")} className={`${head} w-[30%]`}>
              <span className="inline-flex items-center gap-1">
                Price per kg {arrow("price")}
                <InfoTip text="Export value ÷ weight across all its buyers: an average over grades and qualities, not a quote. The dotted line is the median of these suppliers." />
              </span>
            </th>
            <th scope="col" aria-sort={ariaSort("growth")} className={`${head} text-right`}>
              <span className="inline-flex items-center gap-1">Growth / yr {arrow("growth")}</span>
            </th>
            <th scope="col" aria-sort={ariaSort("reach")} className={`${head} text-right`}>
              <span className="inline-flex items-center gap-1">Markets {arrow("reach")}</span>
            </th>
            <th
              scope="col"
              aria-sort={ariaSort("size")}
              className={`${head} text-right ${budgetUsd ? "" : "pr-5"}`}
            >
              <span className="inline-flex items-center gap-1">World share {arrow("size")}</span>
            </th>
            {budgetUsd !== undefined && (
              <th scope="col" className={`${head} pr-5 text-right`}>
                Budget buys
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => {
            const price = s.unit_price_usd_kg;
            return (
              <tr
                key={s.country.code}
                data-supplier={s.country.code}
                tabIndex={-1}
                className={`border-b border-line last:border-0 hover:bg-surface-2/60 ${rowFocus}`}
              >
                <td className="py-3 pr-3 pl-5 align-middle">
                  <span className="flex flex-col items-start gap-1">
                    <span className="font-medium">{s.country.name}</span>
                    <Tags tags={s.tags} />
                  </span>
                </td>
                <td className="px-3 py-3">
                  {price !== null ? (
                    <span className="flex flex-col gap-1.5">
                      <span className="flex items-baseline justify-between gap-2">
                        <span className="font-semibold tabular-nums">{perKg(price)}</span>
                        <span className="text-xs text-muted">{vsMedian(price, median)}</span>
                      </span>
                      <PriceBar price={price} median={median} max={max} />
                    </span>
                  ) : (
                    <span className="text-subtle">No reliable price</span>
                  )}
                </td>
                <td
                  className={`px-3 py-3 text-right tabular-nums ${growthClass(s.exports_growth_3y)}`}
                >
                  {s.exports_growth_3y !== null ? signedPercent(s.exports_growth_3y) : "n/a"}
                </td>
                <td className="px-3 py-3 text-right tabular-nums">{s.markets_served}</td>
                <td className={`px-3 py-3 text-right tabular-nums ${budgetUsd ? "" : "pr-5"}`}>
                  {percent(s.world_share, { floor: true })}
                </td>
                {budgetUsd !== undefined && (
                  <td className="py-3 pr-5 pl-3 text-right font-medium tabular-nums">{buys(s)}</td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* Phones: one compact block per supplier. */}
      <ul className="flex flex-col border-t border-line md:hidden" aria-label="Supplier countries">
        {rows.map((s) => {
          const price = s.unit_price_usd_kg;
          return (
            <li
              key={s.country.code}
              data-supplier={s.country.code}
              tabIndex={-1}
              className={`flex flex-col gap-2 border-b border-line px-4 py-3.5 last:border-0 ${rowFocus}`}
            >
              <div className="flex items-start justify-between gap-3">
                <span className="flex min-w-0 flex-col items-start gap-1">
                  <span className="font-medium">{s.country.name}</span>
                  <Tags tags={s.tags} />
                </span>
                <span className="shrink-0 text-right">
                  <span className="block font-semibold tabular-nums">
                    {price !== null ? perKg(price) : "Price n/a"}
                  </span>
                  {price !== null && (
                    <span className="block text-xs text-muted">{vsMedian(price, median)}</span>
                  )}
                </span>
              </div>
              {price !== null && <PriceBar price={price} median={median} max={max} />}
              <p className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted tabular-nums">
                <span className={growthClass(s.exports_growth_3y)}>
                  {s.exports_growth_3y !== null
                    ? `${signedPercent(s.exports_growth_3y)}/yr`
                    : "Growth n/a"}
                </span>
                <span>{s.markets_served} markets</span>
                <span>{percent(s.world_share, { floor: true })} of world exports</span>
                {budgetUsd !== undefined && (
                  <span className="font-medium text-fg">Budget buys {buys(s)}</span>
                )}
              </p>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
