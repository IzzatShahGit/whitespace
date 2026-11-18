"use client";

import { Anchor, Clock, Fuel, Ship, Truck } from "lucide-react";
import { type ReactNode, useEffect, useId, useState } from "react";

import { Card, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/empty";
import { Segmented } from "@/components/ui/segmented";
import {
  CONTAINER_OPTIONS,
  type CostRange,
  type FreightEstimate as Estimate,
  useFreight,
  useShipping,
} from "@/lib/api/freight";
import { parseKg, perKg, usd, weight } from "@/lib/money";

const km = (n: number) => `${Math.round(n).toLocaleString("en")} km`;

/** Low–high as a bar, with the typical figure marked. Scaled to `max` so rows compare. */
function RangeBar({ range, max }: { range: CostRange; max: number }) {
  const left = (range.low / max) * 100;
  const width = Math.max(((range.high - range.low) / max) * 100, 1);
  const mark = (range.typical / max) * 100;
  return (
    <span aria-hidden className="relative block h-1.5 w-full rounded-full bg-surface-2">
      <span
        className="absolute inset-y-0 rounded-full bg-brand/30"
        style={{ left: `${left}%`, width: `${width}%` }}
      />
      <span
        className="absolute -top-0.5 h-2.5 w-0.5 rounded-full bg-brand"
        style={{ left: `${mark}%` }}
      />
    </span>
  );
}

/** Origin port → destination port, with road legs for landlocked countries. */
function RouteStrip({ e }: { e: Estimate }) {
  const r = e.route;
  const stop = (name: string, sub: string) => (
    <span className="min-w-0 text-center">
      <span className="block truncate text-sm font-medium text-fg">{name}</span>
      <span className="block truncate text-xs text-subtle">{sub}</span>
    </span>
  );
  const leg = (icon: ReactNode, text: string, dashed = false) => (
    <span className="flex min-w-12 flex-1 flex-col items-center gap-1">
      <span className="flex w-full items-center gap-1.5 text-subtle [&>svg]:h-4 [&>svg]:w-4 [&>svg]:shrink-0">
        <span
          className={`h-px flex-1 ${dashed ? "border-t border-dashed border-line-strong" : "bg-line-strong"}`}
        />
        {icon}
        <span
          className={`h-px flex-1 ${dashed ? "border-t border-dashed border-line-strong" : "bg-line-strong"}`}
        />
      </span>
      <span className="text-xs whitespace-nowrap text-muted tabular-nums">{text}</span>
    </span>
  );
  return (
    <div className="flex items-center gap-2 rounded-xl border border-line p-3 sm:gap-3 sm:p-4">
      {r.origin_inland_km > 0 && (
        <>
          {stop(e.origin.name, "inland")}
          {leg(<Truck />, km(r.origin_inland_km), true)}
        </>
      )}
      {stop(r.origin_port, r.origin_inland_km > 0 ? "gateway port" : e.origin.name)}
      {r.sea_nm > 0 && leg(<Ship />, km(r.sea_km))}
      {r.sea_nm > 0 && stop(r.dest_port, r.dest_inland_km > 0 ? "gateway port" : e.dest.name)}
      {r.dest_inland_km > 0 && (
        <>
          {leg(<Truck />, km(r.dest_inland_km), true)}
          {stop(e.dest.name, "inland")}
        </>
      )}
    </div>
  );
}

function Breakdown({ e }: { e: Estimate }) {
  const max = e.total.high;
  const unit = e.container === "lcl" ? "Your shipment" : "Per container";
  const stages = [
    { key: "to_port", title: `To ${e.route.dest_port}`, subtotal: e.to_port },
    { key: "after_arrival", title: "After arrival", subtotal: e.after_arrival },
  ] as const;
  return (
    <table className="w-full text-sm">
      <caption className="sr-only">{unit}: low, typical and high</caption>
      <thead>
        <tr className="text-left text-xs text-subtle">
          <th scope="col" className="pb-2 font-medium">
            {unit}
          </th>
          <th scope="col" className="hidden w-28 pb-2 font-medium sm:table-cell">
            <span className="sr-only">Range</span>
          </th>
          <th scope="col" className="pb-2 text-right font-medium">
            Typical
          </th>
          <th scope="col" className="hidden pb-2 text-right font-medium sm:table-cell">
            Range
          </th>
        </tr>
      </thead>
      {stages.map((stage) => (
        <tbody key={stage.key} className="border-t border-line">
          {e.lines
            .filter((line) => line.stage === stage.key)
            .map((line) => (
              <tr key={line.key}>
                <td className="py-1.5 pr-3 text-muted">{line.label}</td>
                <td className="hidden py-1.5 pr-3 sm:table-cell">
                  <RangeBar range={line.usd} max={max} />
                </td>
                <td className="py-1.5 text-right tabular-nums">{usd(line.usd.typical)}</td>
                <td className="hidden py-1.5 pl-3 text-right text-xs whitespace-nowrap text-subtle tabular-nums sm:table-cell">
                  {usd(line.usd.low)}–{usd(line.usd.high)}
                </td>
              </tr>
            ))}
          <tr className="font-medium">
            <td className="pt-1 pb-3 text-fg">{stage.title}</td>
            <td className="hidden sm:table-cell" />
            <td className="pt-1 pb-3 text-right tabular-nums">{usd(stage.subtotal.typical)}</td>
            <td className="hidden pt-1 pb-3 pl-3 text-right text-xs whitespace-nowrap text-subtle tabular-nums sm:table-cell">
              {usd(stage.subtotal.low)}–{usd(stage.subtotal.high)}
            </td>
          </tr>
        </tbody>
      ))}
    </table>
  );
}

/**
 * What shipping one container costs, from the exporter's port to the buyer: the route,
 * time at sea, and each cost as a low / typical / high range. Not a quote.
 */
export function FreightEstimate({
  origin,
  dest,
  hs6,
  valueUsdKg,
  title = "Shipping estimate",
}: {
  origin: string | undefined;
  dest: string;
  hs6: string;
  valueUsdKg?: number;
  title?: string;
}) {
  const id = useId();
  const shipping = useShipping();
  const freight = useFreight(origin, dest, hs6, shipping.container, shipping.load, valueUsdKg);
  const [loadText, setLoadText] = useState(shipping.load ? String(shipping.load) : "");
  const { setLoad } = shipping;
  const shared = shipping.container === "lcl";

  // Apply a typed load once the user pauses; empty means "typical".
  useEffect(() => {
    const timer = setTimeout(() => {
      const kg = loadText.trim() ? parseKg(loadText) : null;
      if (!loadText.trim() || (kg !== null && kg > 0 && kg <= 30_000)) setLoad(kg);
    }, 500);
    return () => clearTimeout(timer);
  }, [loadText, setLoad]);

  function pickContainer(next: typeof shipping.container) {
    if ((next === "lcl") !== shared) {
      setLoadText("");
      setLoad(null);
    }
    shipping.setContainer(next);
  }

  if (freight.data === null) return null; // no route between these countries
  const e = freight.data;

  return (
    <Card className="p-5 sm:p-6">
      <CardHeader
        icon={<Ship />}
        title={title}
        description={
          e
            ? `${e.origin.name} → ${e.dest.name}, ${e.container === "lcl" ? "a small shipment in a shared container" : "one container"}. A range, not a quote.`
            : "One container, port to port. A range, not a quote."
        }
      />

      <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <Segmented
          label="Container size"
          value={shipping.container}
          onChange={pickContainer}
          items={CONTAINER_OPTIONS}
        />
        <label htmlFor={`${id}-load`} className="flex items-center gap-2 text-sm text-muted">
          {shared ? "Shipment" : "Load"}
          <input
            id={`${id}-load`}
            inputMode="decimal"
            value={loadText}
            onChange={(ev) => setLoadText(ev.target.value)}
            placeholder={e ? String(Math.round(e.kg_per_container)) : "kg"}
            aria-describedby={`${id}-load-hint`}
            className="h-9 w-24 rounded-lg border border-line bg-surface px-2 text-right text-base text-fg tabular-nums outline-none focus:border-brand/60 focus:ring-4 focus:ring-brand/10 sm:text-sm"
          />
          kg
        </label>
      </div>
      {e && (
        <p id={`${id}-load-hint`} className="mt-1.5 text-xs text-subtle sm:text-right">
          {e.kg_basis}: {weight(e.kg_per_container)}
          {e.container === "lcl" ? `, about ${e.volume_m3} m³` : " per container"}
        </p>
      )}

      {freight.isError && (
        <p className="mt-5 text-sm text-muted">Couldn’t estimate shipping right now.</p>
      )}

      {!e && !freight.isError && (
        <div className="mt-5 flex flex-col gap-3" aria-busy>
          <Skeleton className="h-16" />
          <Skeleton className="h-40" />
        </div>
      )}

      {e && (
        <div
          className={`mt-5 flex flex-col gap-5 transition-opacity ${freight.isPlaceholderData ? "opacity-60" : ""}`}
          aria-live="polite"
        >
          <RouteStrip e={e} />

          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div className="rounded-xl bg-surface-2/60 p-3">
              <dt className="flex items-center gap-1.5 text-xs text-muted">
                <Anchor className="h-3.5 w-3.5" aria-hidden /> To {e.route.dest_port}
              </dt>
              <dd className="mt-1 text-lg font-semibold tabular-nums">{usd(e.to_port.typical)}</dd>
              <dd className="text-xs text-subtle tabular-nums">
                {perKg(e.to_port_usd_kg.typical)}
              </dd>
            </div>
            <div className="rounded-xl bg-surface-2/60 p-3">
              <dt className="text-xs text-muted">All-in to the buyer</dt>
              <dd className="mt-1 text-lg font-semibold tabular-nums">{usd(e.total.typical)}</dd>
              <dd className="text-xs text-subtle tabular-nums">
                {perKg(e.total_usd_kg.low)}–{perKg(e.total_usd_kg.high)}
              </dd>
            </div>
            <div className="col-span-2 rounded-xl bg-surface-2/60 p-3 sm:col-span-1">
              <dt className="flex items-center gap-1.5 text-xs text-muted">
                <Clock className="h-3.5 w-3.5" aria-hidden /> Door to door
              </dt>
              <dd className="mt-1 text-lg font-semibold tabular-nums">
                {e.route.days_low}–{e.route.days_high} days
              </dd>
              <dd className="text-xs text-subtle">
                {e.route.sea_nm > 0 ? `${km(e.route.sea_km)} at sea` : "by road/rail"}
              </dd>
            </div>
          </dl>

          <Breakdown e={e} />

          <div className="flex flex-col gap-2 border-t border-line pt-4 text-xs leading-5 text-subtle">
            <p className="flex items-center gap-1.5">
              <Fuel className="h-3.5 w-3.5 shrink-0" aria-hidden />
              Fuel: Brent ${e.fuel.brent_usd.toFixed(0)}
              {e.fuel.as_of ? ` on ${e.fuel.as_of}` : " (reference)"} · container rates set{" "}
              {e.rates_as_of}
              {e.value_basis &&
                ` · insurance on ${perKg(e.value_usd_kg ?? 0)} (${e.value_basis.toLowerCase()})`}
            </p>
            <ul className="flex flex-col gap-1">
              {e.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </Card>
  );
}
