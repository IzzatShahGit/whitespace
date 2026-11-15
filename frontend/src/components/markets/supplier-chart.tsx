"use client";

import { useState } from "react";

import type { Supplier } from "@/lib/api/queries";
import { money, percent, points } from "@/lib/format";

/** Round the axis up to a readable maximum, so small markets aren't squashed. */
function axisMax(shares: number[]): number {
  const top = Math.max(...shares, 0.01);
  return [0.1, 0.25, 0.5, 0.75, 1].find((step) => top <= step) ?? 1;
}

function Dot({ at, tone }: { at: number; tone: "start" | "end" }) {
  return (
    <span
      aria-hidden
      className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-ink-raised"
      style={{ left: `${at}%`, background: `var(--chart-${tone})` }}
    />
  );
}

/**
 * Who supplies this market, and how each supplier's share moved: a dumbbell per
 * supplier (start-year dot, end-year dot, the line between them is the change).
 */
export function SupplierChart({
  suppliers,
  startYear,
  endYear,
  highlight,
}: {
  suppliers: Supplier[];
  startYear: number;
  endYear: number;
  highlight?: string; // the user's exporter country
}) {
  const [asTable, setAsTable] = useState(false);
  const [hovered, setHovered] = useState<string>();
  const max = axisMax(suppliers.flatMap((s) => [s.share_start, s.share_end]));
  const pos = (share: number) => (Math.min(share, max) / max) * 100;
  const ticks = [0, 0.5, 1].map((f) => f * max);

  const legend = (
    <div className="flex items-center gap-4 text-xs text-sage">
      {(["start", "end"] as const).map((tone) => (
        <span key={tone} className="flex items-center gap-1.5">
          <span
            className="h-2.5 w-2.5 rounded-full"
            style={{ background: `var(--chart-${tone})` }}
          />
          {tone === "start" ? startYear : endYear}
        </span>
      ))}
    </div>
  );

  return (
    <figure className="rounded-2xl border border-ink-line bg-ink-raised p-6">
      <figcaption className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="text-lg font-medium">Who supplies this market</h2>
          <p className="text-sm text-sage">
            Share of imports, {startYear} vs {endYear} · largest suppliers in {endYear}
          </p>
        </div>
        <div className="flex items-center gap-4">
          {legend}
          <button
            type="button"
            onClick={() => setAsTable((t) => !t)}
            className="text-xs text-sage underline-offset-4 hover:text-cream hover:underline"
          >
            {asTable ? "Show chart" : "Show as table"}
          </button>
        </div>
      </figcaption>

      {asTable ? (
        <table className="mt-5 w-full text-sm">
          <thead className="text-left text-xs text-sage-dim">
            <tr>
              <th className="pb-2 font-normal">Supplier</th>
              <th className="pb-2 text-right font-normal">{startYear}</th>
              <th className="pb-2 text-right font-normal">{endYear}</th>
              <th className="pb-2 text-right font-normal">Change</th>
              <th className="pb-2 text-right font-normal">Sales {endYear}</th>
            </tr>
          </thead>
          <tbody className="tabular-nums">
            {suppliers.map((s) => (
              <tr key={s.country.code} className="border-t border-ink-line/60">
                <td className="py-2">{s.country.name}</td>
                <td className="py-2 text-right">{percent(s.share_start, { floor: true })}</td>
                <td className="py-2 text-right">{percent(s.share_end, { floor: true })}</td>
                <td className="py-2 text-right">{points(s.share_end - s.share_start)}</td>
                <td className="py-2 text-right">{money(s.value_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="mt-6">
          <ul className="flex flex-col">
            {suppliers.map((s) => {
              const a = pos(s.share_start);
              const b = pos(s.share_end);
              const isYou = s.country.code === highlight;
              const active = hovered === s.country.code;
              return (
                <li
                  key={s.country.code}
                  tabIndex={0}
                  onMouseEnter={() => setHovered(s.country.code)}
                  onMouseLeave={() => setHovered(undefined)}
                  onFocus={() => setHovered(s.country.code)}
                  onBlur={() => setHovered(undefined)}
                  aria-label={`${s.country.name}: ${percent(s.share_start)} in ${startYear}, ${percent(s.share_end)} in ${endYear}`}
                  className={`relative grid grid-cols-[8rem_1fr_3rem] items-center gap-3 rounded-lg px-2 py-2 outline-none sm:grid-cols-[10rem_1fr_3.5rem] ${
                    active ? "bg-ink-line/40" : ""
                  }`}
                >
                  <span className="flex items-center gap-2 truncate text-sm">
                    <span className="truncate">{s.country.name}</span>
                    {isYou && (
                      <span className="shrink-0 rounded-full bg-ember/15 px-1.5 text-[10px] font-medium text-ember">
                        You
                      </span>
                    )}
                  </span>
                  <span className="relative h-6">
                    <span aria-hidden className="absolute inset-x-0 top-1/2 h-px bg-ink-line" />
                    <span
                      aria-hidden
                      className="absolute top-1/2 h-0.5 -translate-y-1/2 bg-sage-dim/70"
                      style={{ left: `${Math.min(a, b)}%`, width: `${Math.abs(b - a)}%` }}
                    />
                    <Dot at={a} tone="start" />
                    <Dot at={b} tone="end" />
                  </span>
                  <span className="text-right text-sm text-cream tabular-nums">
                    {percent(s.share_end, { floor: true })}
                  </span>
                  {active && (
                    <span
                      role="tooltip"
                      className="pointer-events-none absolute -top-9 left-1/2 z-10 -translate-x-1/2 rounded-lg border border-ink-line bg-ink px-3 py-1.5 text-xs whitespace-nowrap shadow-lg"
                    >
                      <span className="font-medium text-cream">
                        {percent(s.share_start, { floor: true })} →{" "}
                        {percent(s.share_end, { floor: true })}
                      </span>
                      <span className="text-sage">
                        {" "}
                        ({points(s.share_end - s.share_start)}) · {money(s.value_usd)} in {endYear}
                      </span>
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
          <div className="mt-2 grid grid-cols-[8rem_1fr_3rem] gap-3 px-2 sm:grid-cols-[10rem_1fr_3.5rem]">
            <span />
            <span className="relative h-4 text-[11px] text-sage-dim">
              {ticks.map((t, i) => (
                <span
                  key={t}
                  className="absolute -translate-x-1/2 tabular-nums"
                  style={{ left: `${i * 50}%` }}
                >
                  {percent(t)}
                </span>
              ))}
            </span>
          </div>
        </div>
      )}
      <p className="mt-4 text-xs text-sage-dim">
        Source: CEPII BACI customs data. Measured, not estimated.
      </p>
    </figure>
  );
}
