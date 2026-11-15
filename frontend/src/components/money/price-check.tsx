"use client";

import { useState } from "react";

import { PriceBars, type PriceRow } from "@/components/markets/price-bars";
import { AmountField, RateNote, useConverter, WeightField } from "@/components/money/amount-field";
import type { Supplier } from "@/lib/api/queries";
import { currencyOf, suggestedCurrencies } from "@/lib/currency";
import { localMoney, parseAmount, parseKg, perKg, usd, weight } from "@/lib/money";

const COMPETITIVE = -0.1; // cost at least 10% under what the market pays
const TIGHT = 0.1;

function Verdict({ cost, average, market }: { cost: number; average: number; market: string }) {
  const gap = cost / average - 1;
  const [tone, text] =
    gap <= COMPETITIVE
      ? [
          "bg-ember/15 text-ember",
          `Your cost is ${Math.round(-gap * 100)}% below what ${market} pays on average: room to compete on price and still earn a margin.`,
        ]
      : gap < TIGHT
        ? [
            "bg-ink-line/60 text-sage",
            `Your cost is close to what ${market} pays on average: margins will be thin once freight and duties are added. Compete on quality, speed or a niche.`,
          ]
        : [
            "bg-caution-bg text-caution",
            `Your cost is ${Math.round(gap * 100)}% above what ${market} pays on average: you'd sell at a loss at today's prices. Look for a premium segment or a market that pays more.`,
          ];
  return <p className={`rounded-xl px-4 py-3 text-sm leading-6 ${tone}`}>{text}</p>;
}

/**
 * "I have stock worth 18 lakh rupees, 5 tonnes: can I compete here?"
 * Converts the user's local money to dollars, works out their cost per kg and sets
 * it against what this market pays each supplier (customs value ÷ weight).
 */
export function PriceCheck({
  exporter,
  market,
  marketName,
  averagePrice,
  suppliers,
}: {
  exporter: string;
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

  const value = parseAmount(valueText);
  const kg = parseKg(qtyText);
  const valueUsd = value !== null ? fx.toUsd(value) : undefined;
  const cost = valueUsd !== undefined && kg ? valueUsd / kg : undefined;
  const revenue = averagePrice && kg ? averagePrice * kg : undefined;

  const rows: PriceRow[] = suppliers
    .filter((s): s is Supplier & { unit_price_usd_kg: number } => s.unit_price_usd_kg !== null)
    .slice(0, 8)
    .map((s) => ({
      code: s.country.code,
      name: s.country.name,
      price: s.unit_price_usd_kg,
      detail: `${Math.round(s.share_end * 100)}% of ${marketName}'s imports`,
    }));
  if (cost !== undefined) rows.push({ code: "YOU", name: "Your cost", price: cost, you: true });

  return (
    <section className="rounded-2xl border border-ink-line bg-ink-raised p-6">
      <h2 className="text-lg font-medium">Can you compete on price?</h2>
      <p className="mt-1 text-sm text-sage">
        Enter your stock in your own currency. We convert it at today’s rate and compare your cost
        per kg with what {marketName} pays each supplier.
      </p>

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <AmountField
          label="Your stock is worth"
          text={valueText}
          onText={setValueText}
          currency={currency}
          onCurrency={setCurrency}
          currencies={currencies}
        />
        <WeightField label="Quantity" text={qtyText} onText={setQtyText} />
      </div>

      {valueUsd !== undefined && value !== null && (
        <div className="rise-in mt-4 grid gap-3 sm:grid-cols-3">
          <Figure label="In US dollars" value={usd(valueUsd)} />
          {cost !== undefined && <Figure label="Your cost" value={perKg(cost)} accent />}
          {revenue !== undefined && kg && (
            <Figure
              label={`At ${marketName}'s average price`}
              value={usd(revenue)}
              note={`${weight(kg)} × ${perKg(averagePrice!)}, before freight and duties${
                fx.toLocal(revenue) && currency !== "USD"
                  ? ` · ${localMoney(fx.toLocal(revenue)!, currency)}`
                  : ""
              }`}
            />
          )}
        </div>
      )}
      {fx.pending && value !== null && (
        <p className="mt-4 text-sm text-sage">Getting today’s rate…</p>
      )}

      {cost !== undefined && averagePrice && (
        <div className="mt-4">
          <Verdict cost={cost} average={averagePrice} market={marketName} />
        </div>
      )}
      {valueUsd !== undefined && !kg && (
        <p className="mt-4 text-sm text-sage">Add the quantity to see your cost per kg.</p>
      )}

      {rows.length > 0 && (
        <div className="mt-6">
          <h3 className="text-sm font-medium">What {marketName} pays each supplier, per kg</h3>
          <div className="mt-3">
            <PriceBars
              rows={rows}
              reference={
                averagePrice ? { label: `${marketName} average`, value: averagePrice } : undefined
              }
            />
          </div>
        </div>
      )}

      <div className="mt-4 flex flex-col gap-1">
        <p className="text-xs text-sage-dim">
          Prices are customs value ÷ weight: an average across grades and qualities, not a quote.
        </p>
        <RateNote currency={currency} />
      </div>
    </section>
  );
}

function Figure({
  label,
  value,
  note,
  accent = false,
}: {
  label: string;
  value: string;
  note?: string;
  accent?: boolean;
}) {
  return (
    <div className="rounded-xl border border-ink-line p-4">
      <p className="text-xs text-sage-dim">{label}</p>
      <p className={`mt-1 text-xl font-semibold tabular-nums ${accent ? "text-ember" : ""}`}>
        {value}
      </p>
      {note && <p className="mt-1 text-xs text-sage">{note}</p>}
    </div>
  );
}
