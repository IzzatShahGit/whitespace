"use client";

import { Anchor, ArrowRight, Calculator, Landmark, Ship, TrendingUp } from "lucide-react";
import Link from "next/link";

import { Badge, Callout } from "@/components/ui/badge";
import { buttonClass } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Stat, StatGroup } from "@/components/ui/stat";
import type { FbaCostItem, FbaEstimate } from "@/lib/api/fba";
import { useRecentMovement } from "@/lib/api/queries";
import { money, percent, signedPercent } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { usd, weight } from "@/lib/money";

const cents = (value: number) => (value < 0 ? `−${usd(-value)}` : usd(value));
const pct = (value: number) => (value < 0 ? `−${percent(-value)}` : percent(value));

/** The headline: verdict, five numbers and where each sale's dollars go. */
export function FbaSummary({ data }: { data: FbaEstimate }) {
  const t = useT();
  const { verdict, profit_unit: profit } = data;
  return (
    <div className="flex flex-col gap-4">
      <Callout tone={verdict.tone}>
        <p className="font-semibold">{verdict.headline}</p>
        {verdict.reasons.map((reason) => (
          <p key={reason} className="mt-1 text-sm">
            {reason}
          </p>
        ))}
      </Callout>
      <StatGroup columns={4}>
        <Stat
          label={t("fba.result.profit")}
          value={cents(profit.typical)}
          changeTone={profit.typical >= 0 ? "positive" : "negative"}
          note={t("fba.result.profitRange", { low: cents(profit.low), high: cents(profit.high) })}
        />
        <Stat
          label={t("fba.result.margin")}
          value={pct(data.margin.typical)}
          explain={t("fba.result.marginExplain")}
          note={
            data.break_even_price
              ? t("fba.result.breakEven", { price: usd(data.break_even_price) })
              : undefined
          }
        />
        <Stat
          label={t("fba.result.cash")}
          value={usd(data.first_order_cash.typical)}
          explain={t("fba.result.cashExplain")}
          note={`${usd(data.first_order_cash.low)} – ${usd(data.first_order_cash.high)}`}
        />
        <Stat
          label={t("fba.result.payback")}
          value={
            data.payback_months === null
              ? t("fba.result.never")
              : t("fba.result.months", { count: data.payback_months })
          }
          explain={t("fba.result.roiExplain")}
          note={`${t("fba.result.roi")}: ${pct(data.roi.typical)}`}
        />
      </StatGroup>
      <SaleSplit data={data} />
    </div>
  );
}

const GROUPS = [
  // Costs in greys and amber, so only the profit reads green.
  { key: "landed", className: "bg-muted" },
  { key: "amazon", className: "bg-subtle" },
  { key: "selling", className: "bg-caution" },
] as const;

/** One bar the width of the price: what each cost group and the profit take. */
function SaleSplit({ data }: { data: FbaEstimate }) {
  const t = useT();
  const price = data.costs.length ? sumTypical(data.costs) + data.profit_unit.typical : 0;
  if (price <= 0) return null;
  const parts = GROUPS.map((g) => ({
    ...g,
    value: sumTypical(data.costs.filter((c) => c.group === g.key)),
  }));
  const profit = data.profit_unit.typical;
  const scale = Math.max(price, sumTypical(data.costs));
  const label = {
    landed: t("fba.result.landed"),
    amazon: t("fba.result.amazon"),
    selling: t("fba.result.selling"),
  };
  return (
    <Card className="p-4 sm:p-5">
      <h3 className="text-sm font-medium text-muted">{t("fba.result.split")}</h3>
      <div
        className="mt-3 flex h-4 overflow-hidden rounded-full bg-surface-2"
        role="img"
        aria-label={parts.map((p) => `${label[p.key]} ${usd(p.value)}`).join(", ")}
      >
        {parts.map((p) => (
          <div
            key={p.key}
            className={p.className}
            style={{ width: `${(p.value / scale) * 100}%` }}
          />
        ))}
        {profit > 0 && (
          <div className="bg-positive" style={{ width: `${(profit / scale) * 100}%` }} />
        )}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-sm">
        {parts.map((p) => (
          <li key={p.key} className="flex items-center gap-2">
            <span className={`h-2.5 w-2.5 rounded-full ${p.className}`} aria-hidden />
            {label[p.key]} <span className="font-medium tabular-nums">{usd(p.value)}</span>
          </li>
        ))}
        <li className="flex items-center gap-2">
          <span
            className={`h-2.5 w-2.5 rounded-full ${profit > 0 ? "bg-positive" : "bg-negative"}`}
            aria-hidden
          />
          {t("fba.result.profitPart")}{" "}
          <span className={`font-medium tabular-nums ${profit < 0 ? "text-negative" : ""}`}>
            {cents(profit)}
          </span>
        </li>
      </ul>
    </Card>
  );
}

const sumTypical = (items: FbaCostItem[]) => items.reduce((sum, c) => sum + c.usd.typical, 0);

/** Every cost per unit sold, in the order it's paid, with the ranges where freight moves. */
export function FbaCosts({
  data,
  price,
  sales,
  plan,
}: {
  data: FbaEstimate;
  price: number;
  sales: number;
  plan: number; // Amazon's Professional plan, a month (from the options endpoint)
}) {
  const t = useT();
  return (
    <Card className="p-4 sm:p-6">
      <CardHeader
        icon={<Calculator />}
        title={t("fba.result.costs")}
        description={t("fba.result.size", {
          tier: data.size.label,
          lb: String(data.size.shipping_weight_lb),
        })}
      />
      <table className="mt-4 w-full text-sm">
        <tbody className="divide-y divide-line">
          {data.costs.map((c) => (
            <tr key={c.key} className="align-top">
              <td className="py-2.5 pe-3">
                <span className="flex items-center gap-2">
                  <span
                    className={`h-2 w-2 shrink-0 rounded-full ${
                      GROUPS.find((g) => g.key === c.group)?.className
                    }`}
                    aria-hidden
                  />
                  {c.label}
                </span>
                {c.note && <span className="mt-0.5 block ps-4 text-xs text-subtle">{c.note}</span>}
              </td>
              <td className="py-2.5 text-end font-medium whitespace-nowrap tabular-nums">
                {usd(c.usd.typical)}
                {c.usd.low !== c.usd.high && (
                  <span className="block text-xs font-normal text-subtle">
                    {usd(c.usd.low)} – {usd(c.usd.high)}
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot className="border-t-2 border-line-strong">
          <tr>
            <td className="pt-3 font-medium">{t("fba.result.total")}</td>
            <td className="pt-3 text-end font-semibold tabular-nums">
              {usd(data.total_cost_unit.typical)}
            </td>
          </tr>
          <tr>
            <td className="pt-1 text-muted">{t("fba.result.price")}</td>
            <td className="pt-1 text-end text-muted tabular-nums">{usd(price)}</td>
          </tr>
          <tr>
            <td className="pt-1 font-medium">{t("fba.result.profitPart")}</td>
            <td
              className={`pt-1 text-end font-semibold tabular-nums ${
                data.profit_unit.typical < 0 ? "text-negative" : "text-positive"
              }`}
            >
              {cents(data.profit_unit.typical)}
            </td>
          </tr>
        </tfoot>
      </table>
      <p className="mt-4 text-sm text-muted">
        {t("fba.result.monthly", {
          amount: cents(data.monthly_profit.typical),
          sales: sales.toLocaleString("en"),
          plan: usd(plan),
        })}
      </p>
    </Card>
  );
}

/** The shipment and the duty: what the order costs to move and to clear US customs. */
export function FbaShipment({ data }: { data: FbaEstimate }) {
  const t = useT();
  const s = data.shipment;
  const duty = data.duty;
  return (
    <Card className="p-4 sm:p-6">
      <CardHeader
        icon={<Ship />}
        title={t("fba.result.shipment")}
        description={s.route ? `${s.route} · ${s.label}` : s.label}
      />
      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
        <div>
          <dt className="text-xs text-muted">{t("fba.result.freightTotal")}</dt>
          <dd className="mt-0.5 font-medium tabular-nums">
            {usd(s.freight_usd.typical)}
            {s.freight_usd.low !== s.freight_usd.high && (
              <span className="block text-xs font-normal text-subtle">
                {usd(s.freight_usd.low)} – {usd(s.freight_usd.high)}
              </span>
            )}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted">{t("fba.result.importFees")}</dt>
          <dd className="mt-0.5 font-medium tabular-nums">{usd(s.import_fees_usd)}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">
            <Anchor className="me-1 inline h-3 w-3" aria-hidden />
            {t("fba.result.load", { m3: String(s.volume_m3), kg: weight(s.kg) })}
          </dt>
          {s.days_low !== null && s.days_high !== null && (
            <dd className="mt-0.5 text-subtle">
              {t("fba.result.transit", { low: String(s.days_low), high: String(s.days_high) })}
            </dd>
          )}
        </div>
      </dl>
      <div className="mt-5 rounded-xl bg-surface-2/70 p-3.5">
        <p className="flex items-center gap-1.5 text-xs font-medium text-muted">
          <Landmark className="h-3.5 w-3.5" aria-hidden /> {t("fba.result.duty")}
        </p>
        <p className="mt-1 text-xl font-semibold tabular-nums">
          {Number(duty.rate_pct.toFixed(1))}%
        </p>
        {duty.additional && duty.additional.length > 0 && (
          <ul className="mt-1.5 flex flex-col gap-1 text-xs text-muted">
            <li>
              {Number(duty.base_pct.toFixed(1))}% {duty.scheme ?? duty.kind}
            </li>
            {duty.additional.map((a) => (
              <li key={a.heading} title={a.heading}>
                + {Number(a.rate_pct.toFixed(1))}% {a.name}
                {a.note && <span className="block text-subtle">{a.note}</span>}
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}

/** US imports of the product by month: is demand growing, and who supplies it today. */
export function FbaDemand({
  origin,
  originName,
  hs6,
}: {
  origin: string;
  originName: string;
  hs6: string;
}) {
  const t = useT();
  const recent = useRecentMovement(origin, hs6, "USA");
  const data = recent.data;
  if (recent.isLoading) return <Card className="h-40 animate-pulse p-6" />;
  const months = data?.months ?? [];
  const last12 = months.slice(-12).reduce((sum, m) => sum + m.total, 0);
  const peak = Math.max(1, ...months.map((m) => m.total));
  // The supplier list covers every country; the endpoint's own share only our exporters.
  const listed = data?.suppliers.find((s) => s.name === originName)?.share_recent;
  const share = listed ?? data?.exporter_share_recent ?? 0;
  return (
    <Card className="p-4 sm:p-6">
      <CardHeader icon={<TrendingUp />} title={t("fba.demand.title")} description={data?.source} />
      {!data || months.length === 0 ? (
        <p className="mt-4 text-sm text-muted">{t("fba.demand.none")}</p>
      ) : (
        <>
          <div className="mt-4 flex flex-wrap items-end gap-x-6 gap-y-2">
            <div>
              <p className="text-xs text-muted">{t("fba.demand.last12")}</p>
              <p className="text-2xl font-semibold tabular-nums">{money(last12)}</p>
            </div>
            {data.change_12m !== null && (
              <Badge tone={data.change_12m >= 0 ? "positive" : "negative"}>
                {t("fba.demand.change", { change: signedPercent(data.change_12m) })}
              </Badge>
            )}
          </div>
          <div className="mt-4 flex h-16 items-end gap-[3px]" aria-hidden>
            {months.map((m) => (
              <div
                key={m.month}
                className="flex-1 rounded-t-sm bg-brand/70"
                style={{ height: `${Math.max(4, (m.total / peak) * 100)}%` }}
                title={`${m.month}: ${money(m.total)}`}
              />
            ))}
          </div>
          {share > 0 && (
            <p className="mt-3 text-sm text-muted">
              {t("fba.demand.share", {
                country: originName,
                share: percent(share, { floor: true }),
              })}
            </p>
          )}
          {data.suppliers.length > 0 && (
            <p className="mt-1 text-xs text-subtle">
              {t("fba.demand.suppliers")}:{" "}
              {data.suppliers
                .slice(0, 4)
                .map((s) => `${s.name} ${percent(s.share_recent, { floor: true })}`)
                .join(" · ")}
            </p>
          )}
        </>
      )}
      <Link
        href={`/app/buy/${hs6}`}
        className={`${buttonClass("secondary", "", "sm")} mt-4 self-start`}
      >
        {t("fba.demand.findSuppliers")} <ArrowRight className="h-3.5 w-3.5" aria-hidden />
      </Link>
    </Card>
  );
}
