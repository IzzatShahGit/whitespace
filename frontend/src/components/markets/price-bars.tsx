"use client";

import type { CSSProperties } from "react";

import { perKg } from "@/lib/money";

export type PriceRow = {
  code: string;
  name: string;
  price: number; // USD per kg
  you?: boolean; // the user's own price: highlighted
  note?: string; // shown at the row end, e.g. "≈ 2.1 t" for a budget
  detail?: string; // a second line under the name, e.g. "25% of imports"
};

const grow = (i: number): CSSProperties =>
  ({ "--delay": `${Math.min(i * 30, 240)}ms`, animationDuration: "500ms" }) as CSSProperties;

/**
 * Price per kg, one bar per country, cheapest first, with a reference line (the median
 * or the market's average). Every value is printed, so the chart is also its own table.
 * `highlight` marks the user's country ("you", in orange) as well as rows with `you`.
 */
export function PriceBars({
  rows,
  reference,
  noteHeader,
  highlight,
}: {
  rows: PriceRow[];
  reference?: { label: string; value: number };
  noteHeader?: string;
  highlight?: string;
}) {
  const sorted = [...rows].sort((a, b) => a.price - b.price);
  const max = Math.max(...sorted.map((r) => r.price), reference?.value ?? 0) * 1.08 || 1;
  const at = (price: number) => (price / max) * 100;
  const columns = noteHeader
    ? "grid-cols-[minmax(0,6.5rem)_minmax(0,1fr)_4.75rem_4rem] sm:grid-cols-[10rem_minmax(0,1fr)_5.5rem_5rem]"
    : "grid-cols-[minmax(0,6.5rem)_minmax(0,1fr)_4.75rem] sm:grid-cols-[10rem_minmax(0,1fr)_5.5rem]";
  const refAt = reference ? at(reference.value) : 0;

  return (
    <div>
      <div className={`grid ${columns} gap-3 pb-1 text-xs text-subtle`}>
        <span />
        <span className="relative h-4">
          {reference && (
            <span
              className="absolute whitespace-nowrap tabular-nums"
              style={{
                left: `${refAt}%`,
                transform: refAt > 60 ? "translateX(calc(-100% - 4px))" : "translateX(4px)",
              }}
            >
              {reference.label}: {perKg(reference.value)}
            </span>
          )}
        </span>
        <span className="text-right">Per kg</span>
        {noteHeader && <span className="text-right">{noteHeader}</span>}
      </div>
      <ul className="flex flex-col" aria-label="Price per kg by country">
        {sorted.map((row, i) => {
          const mine = row.you || (highlight !== undefined && row.code === highlight);
          const vsRef = reference ? row.price / reference.value - 1 : undefined;
          return (
            <li
              key={row.code}
              className={`grid ${columns} items-center gap-3 rounded-lg py-1.5 ${
                mine ? "-mx-2 bg-accent-soft/60 px-2" : ""
              }`}
            >
              <span className="min-w-0">
                <span
                  className={`flex items-center gap-1.5 text-sm ${mine ? "font-medium text-accent-strong" : "text-fg"}`}
                >
                  <span className="truncate">{row.name}</span>
                  {mine && !row.you && (
                    <span className="shrink-0 rounded-full bg-accent-soft px-1.5 text-xs font-medium text-accent-strong">
                      You
                    </span>
                  )}
                </span>
                {row.detail && (
                  <span className="block truncate text-xs text-subtle">{row.detail}</span>
                )}
              </span>
              <span className="relative h-7">
                <span
                  aria-hidden
                  className="grow-x absolute top-1/2 left-0 h-3 -translate-y-1/2 rounded-r-md"
                  style={{
                    ...grow(i),
                    width: `${at(row.price)}%`,
                    background: mine ? "var(--chart-exporter)" : "var(--chart-end)",
                    opacity: mine ? 1 : 0.85,
                  }}
                />
                {reference && (
                  <span
                    aria-hidden
                    className="absolute inset-y-0 border-l border-dashed border-line-strong"
                    style={{ left: `${refAt}%` }}
                  />
                )}
              </span>
              <span className="text-right">
                <span className="block text-sm font-medium tabular-nums">{perKg(row.price)}</span>
                {vsRef !== undefined && reference && (
                  <span className="block text-xs text-subtle tabular-nums">
                    {Math.abs(vsRef) < 0.02
                      ? "≈ 0%"
                      : `${vsRef < 0 ? "−" : "+"}${Math.round(Math.abs(vsRef) * 100)}%`}
                    <span className="sr-only"> compared with the {reference.label}</span>
                  </span>
                )}
              </span>
              {noteHeader && (
                <span className="text-right text-sm text-muted tabular-nums">
                  {row.note ?? "–"}
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
