"use client";

import { BarChart3, Table2, Users } from "lucide-react";
import { type CSSProperties, useState } from "react";

import { Card, CardHeader } from "@/components/ui/card";
import type { Supplier } from "@/lib/api/queries";
import { money, percent, points } from "@/lib/format";

/** Round the axis up to a readable maximum, so small markets aren't squashed. */
function axisMax(shares: number[]): number {
  const top = Math.max(...shares, 0.01);
  return [0.1, 0.25, 0.5, 0.75, 1].find((step) => top <= step) ?? 1;
}

function Change({ value }: { value: number }) {
  const rounded = Math.round(value * 100);
  return (
    <span
      className={`text-xs tabular-nums ${rounded > 0 ? "text-positive" : rounded < 0 ? "text-negative" : "text-subtle"}`}
    >
      {points(value)}
    </span>
  );
}

/**
 * Who supplies this market, and how each supplier's share moved: a dumbbell per supplier
 * (start-year dot, end-year dot, the line between them is the change). The user's
 * country is drawn in orange. A table view carries the same figures.
 */
export function SupplierChart({
  suppliers,
  startYear,
  endYear,
  highlight,
  marketName,
  exporterName,
}: {
  suppliers: Supplier[];
  startYear: number;
  endYear: number;
  highlight?: string; // the user's exporter country
  marketName?: string;
  exporterName?: string;
}) {
  const [asTable, setAsTable] = useState(false);
  const max = axisMax(suppliers.flatMap((s) => [s.share_start, s.share_end]));
  const pos = (share: number) => (Math.min(share, max) / max) * 100;
  const leader = suppliers[0];
  const ownIndex = suppliers.findIndex((s) => s.country.code === highlight);
  const where = marketName ? `${marketName}’s` : "the";

  const title = !leader
    ? "Who supplies this market"
    : ownIndex === 0
      ? `${leader.country.name} is the biggest supplier, with ${percent(leader.share_end)}`
      : `${leader.country.name} leads with ${percent(leader.share_end)} of ${where} imports`;
  const description =
    ownIndex > 0
      ? `${exporterName ?? "Your country"} is #${ownIndex + 1} with ${percent(suppliers[ownIndex].share_end, { floor: true })}, ${points(suppliers[ownIndex].share_end - suppliers[ownIndex].share_start)} since ${startYear}.`
      : ownIndex === -1 && exporterName
        ? `${exporterName} isn’t among the largest suppliers yet. Share of imports, ${startYear} → ${endYear}.`
        : `Share of imports, ${startYear} → ${endYear}, largest suppliers in ${endYear}.`;

  return (
    <Card className="p-5 sm:p-6">
      <CardHeader
        icon={<Users />}
        title={title}
        description={description}
        action={
          <button
            type="button"
            onClick={() => setAsTable((t) => !t)}
            className="inline-flex h-9 items-center gap-1.5 rounded-xl px-2.5 text-sm text-muted transition-colors hover:bg-surface-2 hover:text-fg focus-visible:outline-2 focus-visible:outline-brand"
          >
            {asTable ? <BarChart3 className="h-4 w-4" /> : <Table2 className="h-4 w-4" />}
            <span className="hidden sm:inline">{asTable ? "Chart" : "Table"}</span>
            <span className="sr-only sm:hidden">{asTable ? "Show chart" : "Show as table"}</span>
          </button>
        }
      />

      {asTable ? (
        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[28rem] text-sm">
            <caption className="sr-only">
              Share of {where} imports by supplier, {startYear} and {endYear}
            </caption>
            <thead className="text-left text-xs text-subtle">
              <tr className="border-b border-line">
                <th className="pb-2 font-medium">Supplier</th>
                <th className="pb-2 text-right font-medium">{startYear}</th>
                <th className="pb-2 text-right font-medium">{endYear}</th>
                <th className="pb-2 text-right font-medium">Change</th>
                <th className="pb-2 text-right font-medium">Sales {endYear}</th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {suppliers.map((s) => (
                <tr key={s.country.code} className="border-b border-line/60 last:border-0">
                  <td
                    className={`py-2.5 ${s.country.code === highlight ? "font-medium text-accent-strong" : ""}`}
                  >
                    {s.country.name}
                  </td>
                  <td className="py-2.5 text-right text-muted">
                    {percent(s.share_start, { floor: true })}
                  </td>
                  <td className="py-2.5 text-right">{percent(s.share_end, { floor: true })}</td>
                  <td className="py-2.5 text-right">
                    <Change value={s.share_end - s.share_start} />
                  </td>
                  <td className="py-2.5 text-right text-muted">{money(s.value_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <figure className="mt-5">
          <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
            {(["start", "end"] as const).map((tone) => (
              <span key={tone} className="flex items-center gap-1.5">
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ background: `var(--chart-${tone})` }}
                />
                {tone === "start" ? startYear : endYear}
              </span>
            ))}
            {ownIndex >= 0 && (
              <span className="flex items-center gap-1.5">
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ background: "var(--chart-exporter)" }}
                />
                You, {endYear}
              </span>
            )}
          </div>
          <ul className="flex flex-col">
            {suppliers.map((s, i) => {
              const a = pos(s.share_start);
              const b = pos(s.share_end);
              const you = s.country.code === highlight;
              const change = s.share_end - s.share_start;
              return (
                <li
                  key={s.country.code}
                  aria-label={`${s.country.name}: ${percent(s.share_start, { floor: true })} in ${startYear}, ${percent(s.share_end, { floor: true })} in ${endYear}, sales ${money(s.value_usd)}`}
                  className={`grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 rounded-xl px-2 py-2 sm:grid-cols-[9rem_minmax(0,1fr)_4.5rem_4.5rem] ${
                    you ? "bg-accent-soft/60" : ""
                  }`}
                >
                  <span
                    className={`flex min-w-0 items-center gap-1.5 text-sm ${you ? "font-medium text-accent-strong" : ""}`}
                  >
                    <span className="truncate">{s.country.name}</span>
                    {you && (
                      <span className="shrink-0 rounded-full bg-accent-soft px-1.5 text-xs font-medium">
                        You
                      </span>
                    )}
                  </span>
                  {/* Phones: the figures sit on the name line, the track below. */}
                  <span className="flex items-baseline justify-end gap-2 sm:hidden">
                    <span className="text-sm font-medium tabular-nums">
                      {percent(s.share_end, { floor: true })}
                    </span>
                    <Change value={change} />
                  </span>
                  <span aria-hidden className="relative col-span-2 h-5 sm:col-span-1">
                    <span className="absolute inset-x-0 top-1/2 h-px bg-line" />
                    <span
                      className="grow-x absolute top-1/2 h-0.5 -translate-y-1/2 bg-line-strong/70"
                      style={
                        {
                          left: `${Math.min(a, b)}%`,
                          width: `${Math.abs(b - a)}%`,
                          transformOrigin: b < a ? "right" : "left",
                          animationDuration: "500ms",
                          "--delay": `${Math.min(i * 40, 240)}ms`,
                        } as CSSProperties
                      }
                    />
                    <span
                      className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-surface"
                      style={{ left: `${a}%`, background: "var(--chart-start)" }}
                    />
                    <span
                      className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-surface"
                      style={{
                        left: `${b}%`,
                        background: you ? "var(--chart-exporter)" : "var(--chart-end)",
                      }}
                    />
                  </span>
                  <span className="hidden text-right text-sm font-medium tabular-nums sm:block">
                    {percent(s.share_end, { floor: true })}
                  </span>
                  <span className="hidden text-right sm:block">
                    <Change value={change} />
                  </span>
                </li>
              );
            })}
          </ul>
          <div className="mt-1 grid grid-cols-1 px-2 sm:grid-cols-[9rem_minmax(0,1fr)_4.5rem_4.5rem] sm:gap-x-3">
            <span className="hidden sm:block" />
            <span className="relative h-4 text-xs text-subtle">
              {[0, 0.5, 1].map((f, i) => (
                <span
                  key={f}
                  className="absolute tabular-nums"
                  style={{
                    left: `${f * 100}%`,
                    transform:
                      i === 0 ? "none" : i === 2 ? "translateX(-100%)" : "translateX(-50%)",
                  }}
                >
                  {percent(f * max)}
                </span>
              ))}
            </span>
          </div>
          <figcaption className="mt-4 text-xs text-subtle">
            Share of {where} imports. Source: CEPII BACI customs data, measured, not estimated.
          </figcaption>
        </figure>
      )}
    </Card>
  );
}
