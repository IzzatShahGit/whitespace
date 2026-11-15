"use client";

import { useState } from "react";

import { perKg } from "@/lib/money";

export type PriceRow = {
  code: string;
  name: string;
  price: number; // USD per kg
  you?: boolean; // the user's own price: highlighted
  note?: string; // shown at the row end, e.g. "≈ 2.1 t" for a budget
  detail?: string; // extra tooltip text
};

/**
 * Price per kg, one bar per country, cheapest first, with a reference line
 * (the median or the market's average). Values are printed on every row, so the
 * chart doubles as its own table.
 */
export function PriceBars({
  rows,
  reference,
  noteHeader,
}: {
  rows: PriceRow[];
  reference?: { label: string; value: number };
  noteHeader?: string;
}) {
  const [hovered, setHovered] = useState<string>();
  const sorted = [...rows].sort((a, b) => a.price - b.price);
  const max = Math.max(...sorted.map((r) => r.price), reference?.value ?? 0) * 1.08 || 1;
  const at = (price: number) => `${(price / max) * 100}%`;
  const columns = noteHeader
    ? "grid-cols-[7rem_1fr_4.5rem_4rem] sm:grid-cols-[9rem_1fr_5rem_5rem]"
    : "grid-cols-[7rem_1fr_4.5rem] sm:grid-cols-[9rem_1fr_5rem]";

  return (
    <div>
      {noteHeader && (
        <div className={`grid ${columns} gap-3 px-2 pb-1 text-[11px] text-sage-dim`}>
          <span />
          <span />
          <span className="text-right">Per kg</span>
          <span className="text-right">{noteHeader}</span>
        </div>
      )}
      <ul className="flex flex-col">
        {sorted.map((row) => {
          const active = hovered === row.code;
          const vsRef = reference ? row.price / reference.value - 1 : undefined;
          return (
            <li
              key={row.code}
              tabIndex={0}
              onMouseEnter={() => setHovered(row.code)}
              onMouseLeave={() => setHovered(undefined)}
              onFocus={() => setHovered(row.code)}
              onBlur={() => setHovered(undefined)}
              aria-label={`${row.name}: ${perKg(row.price)}${row.note ? `, ${row.note}` : ""}`}
              className={`relative grid ${columns} items-center gap-3 rounded-lg px-2 py-1.5 outline-none ${
                active ? "bg-ink-line/40" : ""
              }`}
            >
              <span className={`truncate text-sm ${row.you ? "font-medium text-ember" : ""}`}>
                {row.name}
              </span>
              <span className="relative h-5">
                <span
                  aria-hidden
                  className="grow-x absolute top-1/2 left-0 h-2.5 -translate-y-1/2 rounded-r-[4px]"
                  style={{
                    width: at(row.price),
                    background: row.you ? "var(--chart-exporter)" : "var(--chart-start)",
                  }}
                />
                {reference && (
                  <span
                    aria-hidden
                    className="absolute -inset-y-1.5 border-l border-dashed border-sage/60"
                    style={{ left: at(reference.value) }}
                  />
                )}
              </span>
              <span className="text-right text-sm text-cream tabular-nums">{perKg(row.price)}</span>
              {noteHeader && (
                <span className="text-right text-sm text-sage tabular-nums">{row.note ?? "–"}</span>
              )}
              {active && (vsRef !== undefined || row.detail) && (
                <span
                  role="tooltip"
                  className="pointer-events-none absolute -top-8 left-1/2 z-10 -translate-x-1/2 rounded-lg border border-ink-line bg-ink px-3 py-1.5 text-xs whitespace-nowrap shadow-lg"
                >
                  {vsRef !== undefined && reference && (
                    <span className="font-medium text-cream">
                      {Math.abs(vsRef) < 0.02
                        ? `About the ${reference.label}`
                        : `${Math.round(Math.abs(vsRef) * 100)}% ${vsRef < 0 ? "below" : "above"} the ${reference.label}`}
                    </span>
                  )}
                  {row.detail && <span className="text-sage"> · {row.detail}</span>}
                </span>
              )}
            </li>
          );
        })}
      </ul>
      {reference && (
        <p className="mt-2 flex items-center gap-2 px-2 text-xs text-sage-dim">
          <span aria-hidden className="h-3 border-l border-dashed border-sage/60" />
          {reference.label[0].toUpperCase() + reference.label.slice(1)}: {perKg(reference.value)}
        </p>
      )}
    </div>
  );
}
