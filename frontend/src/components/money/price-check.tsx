"use client";

import { CircleCheck, Scale, TriangleAlert, TrendingDown } from "lucide-react";
import { useState } from "react";

import { PriceBars, type PriceRow } from "@/components/markets/price-bars";
import { LandedReceipt } from "@/components/money/landed-cost";
import { AmountField, RateNote, useConverter, WeightField } from "@/components/money/amount-field";
import { Callout } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import { useDuties } from "@/lib/api/landed-cost";
import type { Supplier } from "@/lib/api/queries";
import { currencyOf, suggestedCurrencies } from "@/lib/currency";
import { localMoney, parseAmount, parseKg, perKg, usd, weight } from "@/lib/money";

const COMPETITIVE = -0.1; // cost at least 10% under what the market pays
const TIGHT = 0.1;

function Verdict({ cost, average, market }: { cost: number; average: number; market: string }) {
  const gap = cost / average - 1;
  const [tone, Icon, text] =
    gap <= COMPETITIVE
      ? ([
          "positive",
          CircleCheck,
          `Your cost is ${Math.round(-gap * 100)}% below what ${market} pays on average: room to compete on price and still earn a margin.`,
        ] as const)
      : gap < TIGHT
        ? ([
            "caution",
            TriangleAlert,
            `Your cost is close to what ${market} pays on average: margins will be thin once freight and duties are added. Compete on quality, speed or a niche.`,
          ] as const)
        : ([
            "negative",
            TrendingDown,
            `Your cost is ${Math.round(gap * 100)}% above what ${market} pays on average: you’d sell at a loss at today’s prices. Look for a premium segment or a market that pays more.`,
          ] as const);
  return (
    <Callout tone={tone}>
      <span className="flex gap-2.5">
        <Icon className="mt-1 h-4 w-4 shrink-0" aria-hidden />
        {text}
      </span>
    </Callout>
  );
}

function Figure({
  label,
  value,
  note,
  you = false,
}: {
  label: string;
  value: string;
  note?: string;
  you?: boolean;
}) {
  return (
    <div className="rounded-xl border border-line bg-surface p-3.5">
      <p className="text-xs text-muted">{label}</p>
      <p
        className={`mt-1 text-lg font-semibold tracking-tight tabular-nums ${you ? "text-accent-strong" : ""}`}
      >
        {value}
      </p>
      {note && <p className="mt-0.5 text-xs leading-5 text-muted">{note}</p>}
    </div>
  );
}

/**
 * "I have stock worth 18 lakh rupees, 5 tonnes: can I compete here?"
 * Shows what the market pays each supplier per kg (customs value ÷ weight), then converts
 * the user's own money to dollars and places their cost per kg on the same chart.
 */
export function PriceCheck({
  exporter,
  exporterName,
  hs6,
  market,
  marketName,
  averagePrice,
  suppliers,
}: {
  exporter: string;
  exporterName?: string;
  hs6?: string; // given: adds freight and duty (landed cost) where tariff data exists
  market: string;
  marketName: string;
  averagePrice: number | null;
  suppliers: Supplier[];
}) {
  const home = currencyOf(exporter);
  const currencies = suggestedCurrencies(home, currencyOf(market));
  const [currency, setCurrency] = useState(home);
  const [valueText, setValueText] = useState("");
  const [qtyText, setQtyText] = useState("");
  const fx = useConverter(currency);
  const duties = useDuties(hs6 ? exporter : undefined, hs6 ?? "", market);
  const covered = Boolean(hs6 && duties.data);

  const value = parseAmount(valueText);
  const kg = parseKg(qtyText);
  const valueUsd = value !== null ? fx.toUsd(value) : undefined;
  const cost = valueUsd !== undefined && kg ? valueUsd / kg : undefined;
  const revenue = averagePrice && kg ? averagePrice * kg : undefined;
  const revenueLocal = revenue !== undefined ? fx.toLocal(revenue) : undefined;

  const priced = suppliers.filter(
    (s): s is Supplier & { unit_price_usd_kg: number } => s.unit_price_usd_kg != null,
  );
  const rows: PriceRow[] = priced.slice(0, 8).map((s) => ({
    code: s.country.code,
    name: s.country.name,
    price: s.unit_price_usd_kg,
    detail: `${Math.max(1, Math.round(s.share_end * 100))}% of imports`,
  }));
  if (cost !== undefined) rows.push({ code: "YOU", name: "Your cost", price: cost, you: true });

  const own = priced.find((s) => s.country.code === exporter);
  const ownGap = own && averagePrice ? own.unit_price_usd_kg / averagePrice - 1 : undefined;
  const title = averagePrice
    ? `${marketName} pays ${perKg(averagePrice)} on average`
    : `What ${marketName} pays per kg`;
  const description =
    own && ownGap !== undefined
      ? `${exporterName ?? "Your country"} sells there at ${perKg(own.unit_price_usd_kg)}${
          Math.abs(ownGap) < 0.02
            ? ", about the average."
            : `, ${Math.round(Math.abs(ownGap) * 100)}% ${ownGap < 0 ? "below" : "above"} the average.`
        }`
      : "What each supplier earns per kg, and where your own cost would sit.";

  return (
    <Card className="p-5 sm:p-6">
      <CardHeader icon={<Scale />} title={title} description={description} />

      <div className="mt-6 grid gap-6 lg:grid-cols-[20rem_minmax(0,1fr)] lg:gap-8">
        <div className="flex flex-col gap-4 rounded-2xl bg-surface-2/60 p-4 sm:p-5">
          <div>
            <h3 className="text-sm font-semibold">Can you compete on price?</h3>
            <p className="mt-1 text-sm text-muted">
              Enter your stock in your own currency. We convert it at today’s rate and add your cost
              per kg to the chart.
            </p>
          </div>
          <AmountField
            label="Your stock is worth"
            text={valueText}
            onText={setValueText}
            currency={currency}
            onCurrency={setCurrency}
            currencies={currencies}
          />
          <WeightField label="Quantity" text={qtyText} onText={setQtyText} />

          {fx.pending && value !== null && (
            <p className="text-sm text-muted" role="status">
              Getting today’s rate…
            </p>
          )}
          {valueUsd !== undefined && value !== null && (
            <div className="grid grid-cols-2 gap-2 lg:grid-cols-1" aria-live="polite">
              <Figure label="In US dollars" value={usd(valueUsd)} />
              {cost !== undefined && <Figure label="Your cost" value={perKg(cost)} you />}
              {revenue !== undefined && kg && averagePrice && (
                <div className="col-span-2 lg:col-span-1">
                  <Figure
                    label={`Sold at ${marketName}’s average`}
                    value={usd(revenue)}
                    note={`${weight(kg)} × ${perKg(averagePrice)}, before freight and duties${
                      revenueLocal && currency !== "USD"
                        ? ` · ${localMoney(revenueLocal, currency)}`
                        : ""
                    }`}
                  />
                </div>
              )}
            </div>
          )}
          {valueUsd !== undefined && !kg && (
            <p className="text-sm text-muted">Add the quantity to see your cost per kg.</p>
          )}
          {cost !== undefined && covered && hs6 ? (
            <LandedReceipt
              exporter={exporter}
              hs6={hs6}
              market={market}
              marketName={marketName}
              cost={cost}
            />
          ) : (
            cost !== undefined &&
            averagePrice && <Verdict cost={cost} average={averagePrice} market={marketName} />
          )}
          <RateNote currency={currency} />
        </div>

        <div className="min-w-0">
          {rows.length > 0 ? (
            <PriceBars
              rows={rows}
              highlight={exporter}
              reference={averagePrice ? { label: "Average", value: averagePrice } : undefined}
            />
          ) : (
            <p className="text-sm text-muted">
              Customs records for {marketName} don’t include weights, so there are no prices per kg
              to compare.
            </p>
          )}
          <p className="mt-4 text-xs leading-5 text-subtle">
            Customs value ÷ weight: an average across grades and qualities, not a quote. % compares
            each price with {marketName}’s average.
          </p>
        </div>
      </div>
    </Card>
  );
}
