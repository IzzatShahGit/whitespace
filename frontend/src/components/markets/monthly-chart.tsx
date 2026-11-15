"use client";

import { type KeyboardEvent, type PointerEvent, useRef, useState } from "react";

import type { RecentMovement } from "@/lib/api/queries";
import { amount, monthLabel } from "@/lib/format";

const W = 640;
const H = 220;
const PAD = { top: 16, right: 96, bottom: 28, left: 56 }; // right: room for end labels

function niceMax(value: number): number {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const step = [1, 2, 2.5, 5, 10].find((s) => value <= s * magnitude) ?? 10;
  return step * magnitude;
}

/**
 * Monthly imports on one axis (same currency): all suppliers (solid) and the
 * exporter (dashed, so it's distinguishable without colour). Hover or use the arrow
 * keys for exact values.
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
  const svg = useRef<SVGSVGElement>(null);
  const points = data.months;
  const max = niceMax(Math.max(...points.map((p) => p.total)));
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;
  const x = (i: number) => PAD.left + (points.length > 1 ? (i / (points.length - 1)) * innerW : 0);
  const y = (v: number) => PAD.top + innerH - (v / max) * innerH;
  const path = (key: "total" | "exporter") =>
    points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[key]).toFixed(1)}`).join("");
  const last = points.length - 1;

  function onPointer(event: PointerEvent<SVGRectElement>) {
    const box = svg.current?.getBoundingClientRect();
    if (!box) return;
    const relative = ((event.clientX - box.left) / box.width) * W;
    const index = Math.round(((relative - PAD.left) / innerW) * last);
    setActive(Math.max(0, Math.min(last, index)));
  }

  function onKey(event: KeyboardEvent<SVGSVGElement>) {
    if (event.key === "ArrowRight") setActive((i) => Math.min(last, (i ?? -1) + 1));
    if (event.key === "ArrowLeft") setActive((i) => Math.max(0, (i ?? last + 1) - 1));
    if (event.key === "Escape") setActive(undefined);
  }

  const legend = (
    <div className="flex items-center gap-4 text-xs text-sage">
      <span className="flex items-center gap-1.5">
        <svg width="18" height="6" aria-hidden>
          <line x1="0" y1="3" x2="18" y2="3" stroke="var(--chart-end)" strokeWidth="2" />
        </svg>
        All suppliers
      </span>
      <span className="flex items-center gap-1.5">
        <svg width="18" height="6" aria-hidden>
          <line
            x1="0"
            y1="3"
            x2="18"
            y2="3"
            stroke="var(--chart-exporter)"
            strokeWidth="2"
            strokeDasharray="4 3"
          />
        </svg>
        {exporterName}
      </span>
    </div>
  );

  if (asTable) {
    return (
      <div>
        <div className="flex items-center justify-between">
          {legend}
          <button
            type="button"
            onClick={() => setAsTable(false)}
            className="text-xs text-sage underline-offset-4 hover:text-cream hover:underline"
          >
            Show chart
          </button>
        </div>
        <div className="mt-3 max-h-72 overflow-auto">
          <table className="w-full text-sm tabular-nums">
            <thead className="sticky top-0 bg-ink-raised text-left text-xs text-sage-dim">
              <tr>
                <th className="pb-2 font-normal">Month</th>
                <th className="pb-2 text-right font-normal">All suppliers</th>
                <th className="pb-2 text-right font-normal">{exporterName}</th>
              </tr>
            </thead>
            <tbody>
              {[...points].reverse().map((p) => (
                <tr key={p.month} className="border-t border-ink-line/60">
                  <td className="py-1.5">{monthLabel(p.month)}</td>
                  <td className="py-1.5 text-right">{amount(p.total, data.currency)}</td>
                  <td className="py-1.5 text-right">{amount(p.exporter, data.currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  const hovered = active !== undefined ? points[active] : undefined;
  return (
    <div>
      <div className="flex items-center justify-between">
        {legend}
        <button
          type="button"
          onClick={() => setAsTable(true)}
          className="text-xs text-sage underline-offset-4 hover:text-cream hover:underline"
        >
          Show as table
        </button>
      </div>
      <div className="relative mt-3">
        <svg
          ref={svg}
          viewBox={`0 0 ${W} ${H}`}
          className="w-full outline-none"
          role="img"
          aria-label={`Monthly imports, ${monthLabel(points[0].month)} to ${monthLabel(points[last].month)}. Use left and right arrow keys for values.`}
          tabIndex={0}
          onKeyDown={onKey}
          onBlur={() => setActive(undefined)}
        >
          {[0, 0.5, 1].map((f) => (
            <g key={f}>
              <line
                x1={PAD.left}
                x2={W - PAD.right}
                y1={y(max * f)}
                y2={y(max * f)}
                stroke="var(--ink-line)"
                strokeWidth="1"
              />
              <text
                x={PAD.left - 8}
                y={y(max * f) + 4}
                textAnchor="end"
                className="fill-sage-dim text-[11px] tabular-nums"
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
              className="fill-sage-dim text-[11px]"
            >
              {monthLabel(points[i].month, true)}
            </text>
          ))}

          <path d={path("total")} fill="none" stroke="var(--chart-end)" strokeWidth="2" />
          <path
            d={path("exporter")}
            fill="none"
            stroke="var(--chart-exporter)"
            strokeWidth="2"
            strokeDasharray="5 4"
          />
          {/* direct labels at the line ends */}
          <text x={x(last) + 8} y={y(points[last].total) + 4} className="fill-cream text-[11px]">
            All suppliers
          </text>
          <text
            x={x(last) + 8}
            y={Math.min(y(points[last].exporter) + 4, H - PAD.bottom)}
            className="fill-cream text-[11px]"
          >
            {exporterName}
          </text>

          {hovered && active !== undefined && (
            <g aria-hidden>
              <line
                x1={x(active)}
                x2={x(active)}
                y1={PAD.top}
                y2={H - PAD.bottom}
                stroke="var(--sage-dim)"
                strokeWidth="1"
              />
              <circle
                cx={x(active)}
                cy={y(hovered.total)}
                r="4.5"
                fill="var(--chart-end)"
                stroke="var(--ink-raised)"
                strokeWidth="2"
              />
              <circle
                cx={x(active)}
                cy={y(hovered.exporter)}
                r="4.5"
                fill="var(--chart-exporter)"
                stroke="var(--ink-raised)"
                strokeWidth="2"
              />
            </g>
          )}
          <rect
            x={PAD.left}
            y={PAD.top}
            width={innerW}
            height={innerH}
            fill="transparent"
            onPointerMove={onPointer}
            onPointerLeave={() => setActive(undefined)}
          />
        </svg>
        {hovered && active !== undefined && (
          <div
            role="tooltip"
            className="pointer-events-none absolute top-0 rounded-lg border border-ink-line bg-ink px-3 py-2 text-xs shadow-lg"
            style={{
              left: `${(x(active) / W) * 100}%`,
              transform: active > last / 2 ? "translateX(calc(-100% - 12px))" : "translateX(12px)",
            }}
          >
            <p className="text-sage-dim">{monthLabel(hovered.month)}</p>
            <p className="mt-1 font-medium text-cream tabular-nums">
              {amount(hovered.total, data.currency)}{" "}
              <span className="font-normal text-sage">all suppliers</span>
            </p>
            <p className="font-medium text-cream tabular-nums">
              {amount(hovered.exporter, data.currency)}{" "}
              <span className="font-normal text-sage">{exporterName}</span>
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
