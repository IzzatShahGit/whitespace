"use client";

import { BarChart3, Table2 } from "lucide-react";
import { type KeyboardEvent, type PointerEvent, useCallback, useId, useState } from "react";

import type { RecentMovement } from "@/lib/api/queries";
import { amount, monthLabel } from "@/lib/format";

const H = 230;

function niceMax(value: number): number {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const step = [1, 2, 2.5, 5, 10].find((s) => value <= s * magnitude) ?? 10;
  return step * magnitude;
}

/** The element's width in CSS pixels, so SVG text renders at its real size (12px+). */
function useWidth() {
  const [width, setWidth] = useState(0);
  const ref = useCallback((el: HTMLDivElement | null) => {
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width)));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return [ref, width] as const;
}

/**
 * Monthly imports on one axis (same currency): all suppliers (green, shaded) and the
 * exporter (orange), each labelled at its end. Hover, or focus and use the arrow keys,
 * for exact values; a table view carries the same figures.
 */
export function MonthlyChart({
  data,
  exporterName,
}: {
  data: RecentMovement;
  exporterName: string;
}) {
  const [active, setActive] = useState<number>();
  const [asTable, setAsTable] = useState(false);
  const [box, width] = useWidth();
  const describedBy = useId();
  const points = data.months;
  const last = points.length - 1;
  const narrow = width < 480;
  const pad = { top: 12, right: narrow ? 12 : 104, bottom: 28, left: 52 };
  const max = niceMax(Math.max(...points.map((p) => p.total)));
  const innerW = Math.max(width - pad.left - pad.right, 1);
  const innerH = H - pad.top - pad.bottom;
  const x = (i: number) => pad.left + (last > 0 ? (i / last) * innerW : 0);
  const y = (v: number) => pad.top + innerH - (v / max) * innerH;
  const line = (key: "total" | "exporter") =>
    points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[key]).toFixed(1)}`).join("");
  const area = `${line("total")}L${x(last).toFixed(1)},${y(0)}L${x(0).toFixed(1)},${y(0)}Z`;

  function onPointer(event: PointerEvent<SVGRectElement>) {
    const rect = event.currentTarget.ownerSVGElement?.getBoundingClientRect();
    if (!rect) return;
    const index = Math.round(((event.clientX - rect.left - pad.left) / innerW) * last);
    setActive(Math.max(0, Math.min(last, index)));
  }

  function onKey(event: KeyboardEvent<SVGSVGElement>) {
    if (event.key === "ArrowRight") setActive((i) => Math.min(last, (i ?? -1) + 1));
    else if (event.key === "ArrowLeft") setActive((i) => Math.max(0, (i ?? last + 1) - 1));
    else if (event.key === "Escape") setActive(undefined);
    else return;
    event.preventDefault();
  }

  const hovered = active !== undefined ? points[active] : undefined;
  const legend = (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
      <span className="flex items-center gap-1.5">
        <span className="h-0.5 w-4 rounded-full" style={{ background: "var(--chart-end)" }} />
        All suppliers
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-0.5 w-4 rounded-full" style={{ background: "var(--chart-exporter)" }} />
        {exporterName}
      </span>
    </div>
  );

  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        {legend}
        <button
          type="button"
          onClick={() => setAsTable((t) => !t)}
          className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-xl px-2.5 text-sm text-muted transition-colors hover:bg-surface-2 hover:text-fg focus-visible:outline-2 focus-visible:outline-brand"
        >
          {asTable ? <BarChart3 className="h-4 w-4" /> : <Table2 className="h-4 w-4" />}
          {asTable ? "Chart" : "Table"}
        </button>
      </div>

      {asTable ? (
        <div className="mt-3 max-h-72 overflow-auto">
          <table className="w-full text-sm tabular-nums">
            <caption className="sr-only">Monthly imports in {data.currency}</caption>
            <thead className="sticky top-0 bg-surface text-left text-xs text-subtle">
              <tr className="border-b border-line">
                <th className="py-2 font-medium">Month</th>
                <th className="py-2 text-right font-medium">All suppliers</th>
                <th className="py-2 text-right font-medium">{exporterName}</th>
              </tr>
            </thead>
            <tbody>
              {[...points].reverse().map((p) => (
                <tr key={p.month} className="border-b border-line/60 last:border-0">
                  <td className="py-2">{monthLabel(p.month)}</td>
                  <td className="py-2 text-right">{amount(p.total, data.currency)}</td>
                  <td className="py-2 text-right">{amount(p.exporter, data.currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div ref={box} className="relative mt-3" style={{ height: H }}>
          {width > 0 && (
            <svg
              width={width}
              height={H}
              viewBox={`0 0 ${width} ${H}`}
              className="rounded-lg outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
              role="img"
              aria-label={`Monthly imports, ${monthLabel(points[0].month)} to ${monthLabel(points[last].month)}. Use the left and right arrow keys to read each month.`}
              aria-describedby={describedBy}
              tabIndex={0}
              onKeyDown={onKey}
              onBlur={() => setActive(undefined)}
            >
              {[0, 0.5, 1].map((f) => (
                <g key={f}>
                  <line
                    x1={pad.left}
                    x2={width - pad.right}
                    y1={y(max * f)}
                    y2={y(max * f)}
                    stroke="var(--chart-grid)"
                  />
                  <text
                    x={pad.left - 8}
                    y={y(max * f) + 4}
                    textAnchor="end"
                    className="fill-subtle text-xs tabular-nums"
                  >
                    {amount(max * f, data.currency)}
                  </text>
                </g>
              ))}
              {[0, Math.floor(last / 2), last].map((i) => (
                <text
                  key={i}
                  x={x(i)}
                  y={H - 8}
                  textAnchor={i === 0 ? "start" : i === last ? "end" : "middle"}
                  className="fill-subtle text-xs"
                >
                  {monthLabel(points[i].month, true)}
                </text>
              ))}

              <path d={area} fill="var(--chart-end)" fillOpacity={0.08} />
              <path
                d={line("total")}
                fill="none"
                stroke="var(--chart-end)"
                strokeWidth="2"
                strokeLinejoin="round"
              />
              <path
                d={line("exporter")}
                fill="none"
                stroke="var(--chart-exporter)"
                strokeWidth="2"
                strokeLinejoin="round"
              />
              {!narrow && (
                <>
                  <text x={x(last) + 8} y={y(points[last].total) + 4} className="fill-fg text-xs">
                    All suppliers
                  </text>
                  <text
                    x={x(last) + 8}
                    y={Math.min(y(points[last].exporter) + 4, H - pad.bottom)}
                    className="fill-accent-strong text-xs font-medium"
                  >
                    {exporterName}
                  </text>
                </>
              )}

              {hovered && active !== undefined && (
                <g aria-hidden>
                  <line
                    x1={x(active)}
                    x2={x(active)}
                    y1={pad.top}
                    y2={H - pad.bottom}
                    stroke="var(--line-strong)"
                    strokeDasharray="3 3"
                  />
                  <circle
                    cx={x(active)}
                    cy={y(hovered.total)}
                    r="4.5"
                    fill="var(--chart-end)"
                    stroke="var(--surface)"
                    strokeWidth="2"
                  />
                  <circle
                    cx={x(active)}
                    cy={y(hovered.exporter)}
                    r="4.5"
                    fill="var(--chart-exporter)"
                    stroke="var(--surface)"
                    strokeWidth="2"
                  />
                </g>
              )}
              <rect
                x={pad.left}
                y={pad.top}
                width={innerW}
                height={innerH}
                fill="transparent"
                onPointerMove={onPointer}
                onPointerDown={onPointer}
                onPointerLeave={() => setActive(undefined)}
              />
            </svg>
          )}
          <div id={describedBy} aria-live="polite" className="sr-only">
            {hovered
              ? `${monthLabel(hovered.month)}: ${amount(hovered.total, data.currency)} from all suppliers, ${amount(hovered.exporter, data.currency)} from ${exporterName}`
              : ""}
          </div>
          {hovered && active !== undefined && (
            <div
              aria-hidden
              className="pointer-events-none absolute top-0 rounded-xl border border-line bg-surface px-3 py-2 text-xs shadow-pop"
              style={{
                left: x(active),
                transform:
                  active > last / 2 ? "translateX(calc(-100% - 12px))" : "translateX(12px)",
              }}
            >
              <p className="text-subtle">{monthLabel(hovered.month)}</p>
              <p className="mt-1 font-medium text-fg tabular-nums">
                {amount(hovered.total, data.currency)}{" "}
                <span className="font-normal text-muted">all suppliers</span>
              </p>
              <p className="font-medium text-accent-strong tabular-nums">
                {amount(hovered.exporter, data.currency)}{" "}
                <span className="font-normal text-muted">{exporterName}</span>
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
