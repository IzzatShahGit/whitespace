"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { type CSSProperties, type ReactNode, use, useState } from "react";

import { PriceBars } from "@/components/markets/price-bars";
import { AmountField, RateNote, useConverter } from "@/components/money/amount-field";
import { Loading, Problem } from "@/components/views/states";
import {
  ApiError,
  type SourcingPick,
  type SupplierOption,
  useProfile,
  useSourcing,
} from "@/lib/api/queries";
import { money, percent, shortProductName, signedPercent } from "@/lib/format";
import { currencyOf, suggestedCurrencies } from "@/lib/currency";
import { parseAmount, perKg, usd, weight } from "@/lib/money";

const delay = (ms: number) => ({ "--delay": `${ms}ms` }) as CSSProperties;

const toneStyles = {
  positive: "bg-ember/15 text-ember",
  neutral: "bg-ink-line/60 text-sage",
  negative: "bg-caution-bg text-caution",
} as const;

function PickIcon({ kind }: { kind: SourcingPick["kind"] }) {
  const paths: Record<SourcingPick["kind"], ReactNode> = {
    best_value: <path d="M8 2v12M11 4.5H6.8a2 2 0 0 0 0 4h2.4a2 2 0 0 1 0 4H5" />,
    most_established: <path d="M8 2 3 4v4c0 3 2.2 5 5 6 2.8-1 5-3 5-6V4L8 2Z" />,
    rising: <path d="M2.5 11.5 6.5 7.5l2.5 2.5 4.5-5M10 5h3.5v3.5" />,
    current: <path d="M3 8.5 6.5 12 13 4.5" />,
  };
  return (
    <svg
      viewBox="0 0 16 16"
      className="h-4 w-4"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      {paths[kind]}
    </svg>
  );
}

function PickCard({ pick }: { pick: SourcingPick }) {
  const accent = pick.kind === "best_value";
  return (
    <div
      className={`flex h-full flex-col gap-2 rounded-2xl border bg-ink-raised p-5 ${
        accent ? "border-ember/40" : "border-ink-line"
      }`}
    >
      <p
        className={`flex items-center gap-1.5 text-xs font-medium ${accent ? "text-ember" : "text-sage"}`}
      >
        <PickIcon kind={pick.kind} />
        {pick.title}
      </p>
      <h3 className="text-lg font-medium">{pick.country.name}</h3>
      <p className="text-sm leading-6 text-sage">{pick.reason}</p>
    </div>
  );
}

function SupplierRow({ option, budgetUsd }: { option: SupplierOption; budgetUsd?: number }) {
  const price = option.unit_price_usd_kg;
  return (
    <li className="flex flex-col gap-3 rounded-2xl border border-ink-line bg-ink-raised p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-sage-dim tabular-nums">#{option.rank}</span>
          <h3 className="font-medium">{option.country.name}</h3>
          {option.tags.map((tag) => (
            <span
              key={tag}
              className="rounded-full bg-ember/15 px-2 py-0.5 text-[11px] font-medium text-ember"
            >
              {tag}
            </span>
          ))}
        </div>
        <p className="text-lg font-semibold tabular-nums">
          {price !== null ? perKg(price) : "Price n/a"}
        </p>
      </div>
      <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <Stat label="World exports" value={money(option.exports_usd)} />
        <Stat label="World share" value={percent(option.world_share, { floor: true })} />
        <Stat
          label="Growth / yr"
          value={
            option.exports_growth_3y !== null ? signedPercent(option.exports_growth_3y) : "n/a"
          }
        />
        <Stat
          label={budgetUsd ? "Your budget buys" : "Markets served"}
          value={
            budgetUsd && price ? `≈ ${weight(budgetUsd / price)}` : String(option.markets_served)
          }
        />
      </dl>
      <ul className="flex flex-wrap gap-2">
        {option.signals.map((s) => (
          <li key={s.text} className={`rounded-full px-2.5 py-1 text-xs ${toneStyles[s.tone]}`}>
            {s.text}
          </li>
        ))}
      </ul>
    </li>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-sage-dim">{label}</dt>
      <dd className="mt-0.5 text-cream tabular-nums">{value}</dd>
    </div>
  );
}

const STEPS = [
  ["Shortlist", "Pick two or three countries from the picks above: one cheap, one established."],
  [
    "Find exporters",
    "Ask each country’s trade promotion office or chamber of commerce for verified exporters.",
  ],
  [
    "Compare quotes",
    "Request samples and FOB quotes. Anything far below the price here deserves questions.",
  ],
  ["Check landed cost", "Add freight, insurance and your import duty before you decide."],
  ["Pay safely", "Start with a small order, paid by letter of credit or escrow."],
] as const;

/** Where to buy a product: picks, prices per kg, budget, and who supplies you today. */
export function SourcingView({ params }: { params: Promise<{ hs6: string }> }) {
  const { hs6 } = use(params);
  const profile = useProfile();
  const fromUrl = useSearchParams().get("buyer")?.toUpperCase();
  const buyer = fromUrl ?? profile.data?.exporter.code;
  const page = useSourcing(buyer, hs6);

  const home = currencyOf(buyer);
  const [currency, setCurrency] = useState<string>();
  const [budgetText, setBudgetText] = useState("");
  const activeCurrency = currency ?? home;
  const fx = useConverter(activeCurrency);

  if (profile.isPending || (buyer && page.isPending)) return <Loading />;
  if (!buyer) {
    return (
      <Problem
        title="Tell us where you’re based first"
        action={{ href: "/onboarding", label: "Set up your preferences →" }}
      />
    );
  }
  if (page.isError || !page.data) {
    const missing = page.error instanceof ApiError && page.error.status === 404;
    return (
      <Problem
        title={missing ? "No supplier data for this product" : "Couldn’t load suppliers"}
        action={{ href: "/app/buy", label: "Search another product" }}
      >
        {missing ? page.error?.message : "Please refresh the page."}
      </Problem>
    );
  }

  const data = page.data;
  const budget = parseAmount(budgetText);
  const budgetUsd = budget !== null ? fx.toUsd(budget) : undefined;
  const priced = data.suppliers.filter(
    (s): s is SupplierOption & { unit_price_usd_kg: number } => s.unit_price_usd_kg !== null,
  );

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-10 px-6 py-12">
      <div className="rise-in">
        <Link href="/app/buy" className="text-sm text-sage hover:text-cream">
          ← Buy something else
        </Link>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight sm:text-3xl">
          Where to buy {data.product.name}
        </h1>
        <p className="mt-2 text-sage">
          The world’s main suppliers for buyers in {data.buyer.name}, compared on price, reliability
          and momentum · {shortProductName(data.product.description)} (HS {data.product.hs6})
        </p>
      </div>

      {data.picks.length > 0 && (
        <section className="rise-in grid gap-4 sm:grid-cols-2 lg:grid-cols-4" style={delay(60)}>
          {data.picks.map((pick) => (
            <PickCard key={pick.kind} pick={pick} />
          ))}
        </section>
      )}

      <section
        className="rise-in grid gap-6 rounded-2xl border border-ink-line bg-ink-raised p-6 lg:grid-cols-[18rem_1fr]"
        style={delay(120)}
      >
        <div className="flex flex-col gap-4">
          <div>
            <h2 className="text-lg font-medium">Price per kg</h2>
            <p className="mt-1 text-sm text-sage">
              What each country charges its buyers, on average. Add your budget to see how much it
              buys.
            </p>
          </div>
          <AmountField
            label="Your budget"
            text={budgetText}
            onText={setBudgetText}
            currency={activeCurrency}
            onCurrency={setCurrency}
            currencies={suggestedCurrencies(home)}
          />
          {budgetUsd !== undefined && (
            <p className="rise-in text-sm text-sage">
              ≈ <span className="font-semibold text-cream">{usd(budgetUsd)}</span>
              {data.median_price_usd_kg && (
                <> · about {weight(budgetUsd / data.median_price_usd_kg)} at the median price</>
              )}
            </p>
          )}
          <RateNote currency={activeCurrency} />
        </div>
        {priced.length > 0 ? (
          <PriceBars
            rows={priced.map((s) => ({
              code: s.country.code,
              name: s.country.name,
              price: s.unit_price_usd_kg,
              note: budgetUsd ? `≈ ${weight(budgetUsd / s.unit_price_usd_kg)}` : undefined,
              detail: `sells to ${s.markets_served} markets`,
            }))}
            reference={
              data.median_price_usd_kg
                ? { label: "median", value: data.median_price_usd_kg }
                : undefined
            }
            noteHeader={budgetUsd ? "You get" : undefined}
          />
        ) : (
          <p className="text-sm text-sage">No reliable prices for this product.</p>
        )}
      </section>

      {data.current_suppliers.length > 0 && (
        <section className="rise-in flex flex-col gap-3" style={delay(160)}>
          <h2 className="text-xl font-semibold tracking-tight">
            Who supplies {data.buyer.name} today
          </h2>
          <ul className="flex flex-col gap-2">
            {data.current_suppliers.map((c) => (
              <li
                key={c.country.code}
                className="grid grid-cols-[9rem_1fr_7rem] items-center gap-3"
              >
                <span className="truncate text-sm">{c.country.name}</span>
                <span className="relative h-2.5 rounded-full bg-ink-line/50">
                  <span
                    className="grow-x absolute inset-y-0 left-0 rounded-full"
                    style={{ width: `${c.share * 100}%`, background: "var(--chart-end)" }}
                  />
                </span>
                <span className="text-right text-sm text-sage tabular-nums">
                  {percent(c.share, { floor: true })}
                  {c.unit_price_usd_kg !== null && ` · ${perKg(c.unit_price_usd_kg)}`}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="rise-in flex flex-col gap-4" style={delay(200)}>
        <h2 className="text-xl font-semibold tracking-tight">Every supplier, compared</h2>
        <ul className="flex flex-col gap-3">
          {data.suppliers.map((option) => (
            <SupplierRow key={option.country.code} option={option} budgetUsd={budgetUsd} />
          ))}
        </ul>
      </section>

      <section className="rise-in rounded-2xl border border-ink-line p-6" style={delay(240)}>
        <h2 className="text-lg font-medium">Your next steps</h2>
        <ol className="mt-4 grid gap-4 sm:grid-cols-5">
          {STEPS.map(([title, text], i) => (
            <li key={title} className="flex flex-col gap-1">
              <span className="text-xs font-medium text-ember tabular-nums">Step {i + 1}</span>
              <span className="text-sm font-medium">{title}</span>
              <span className="text-xs leading-5 text-sage">{text}</span>
            </li>
          ))}
        </ol>
      </section>

      <p className="text-xs text-sage-dim">
        Customs data {data.data_year} (CEPII BACI). Prices are export value ÷ weight across all
        buyers: an average over grades and qualities, not a quote.
      </p>
    </main>
  );
}
