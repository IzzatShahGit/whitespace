"use client";

import { LeadsPanel } from "@/components/leads/leads-panel";
import { FreightEstimate } from "@/components/money/freight-estimate";
import { Segmented } from "@/components/ui/segmented";
import {
  ArrowLeft,
  ListChecks,
  MapPin,
  PackageX,
  RotateCcw,
  Scale,
  Sparkles,
  Truck,
  Wallet,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { type CSSProperties, use, useState } from "react";

import { NextSteps } from "@/components/buy/next-steps";
import { PickCard } from "@/components/buy/picks";
import { SupplierTable } from "@/components/buy/supplier-table";
import { AmountField, RateNote, useConverter } from "@/components/money/amount-field";
import { Button, ButtonLink } from "@/components/ui/button";
import { Card, CardHeader, Page, PageHeader } from "@/components/ui/card";
import { EmptyState, Skeleton } from "@/components/ui/empty";
import {
  ApiError,
  type SourcingPage,
  type SupplierOption,
  useProfile,
  useSourcing,
} from "@/lib/api/queries";
import { currencyOf, suggestedCurrencies } from "@/lib/currency";
import { capitalize, percent, shortProductName } from "@/lib/format";
import { parseAmount, perKg, usd, weight } from "@/lib/money";

const delay = (ms: number) => ({ "--delay": `${ms}ms` }) as CSSProperties;

function BackLink() {
  return (
    <Link
      href="/app/buy"
      className="inline-flex items-center gap-1.5 rounded-lg text-sm text-muted hover:text-fg focus-visible:outline-2 focus-visible:outline-brand"
    >
      <ArrowLeft className="h-4 w-4" /> Buy
    </Link>
  );
}

function SourcingSkeleton() {
  return (
    <Page aria-busy>
      <div className="flex flex-col gap-3">
        <Skeleton className="h-5 w-16" />
        <Skeleton className="h-9 w-72" />
        <Skeleton className="h-5 w-full max-w-xl" />
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-44 rounded-2xl" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
        <Skeleton className="h-[28rem] rounded-2xl" />
        <Skeleton className="h-72 rounded-2xl" />
      </div>
    </Page>
  );
}

function Budget({
  data,
  budgetText,
  setBudgetText,
  currency,
  setCurrency,
  home,
  budgetUsd,
  priced,
}: {
  data: SourcingPage;
  budgetText: string;
  setBudgetText: (t: string) => void;
  currency: string;
  setCurrency: (c: string) => void;
  home: string;
  budgetUsd?: number;
  priced: (SupplierOption & { unit_price_usd_kg: number })[];
}) {
  const cheapest = priced.reduce<(typeof priced)[number] | undefined>(
    (best, s) => (!best || s.unit_price_usd_kg < best.unit_price_usd_kg ? s : best),
    undefined,
  );
  return (
    <Card className="flex flex-col gap-4 p-5">
      <CardHeader
        icon={<Wallet />}
        title="Your budget"
        description="See how much it buys from each country."
      />
      <AmountField
        label="Amount to spend"
        text={budgetText}
        onText={setBudgetText}
        currency={currency}
        onCurrency={setCurrency}
        currencies={suggestedCurrencies(home)}
      />
      {budgetUsd !== undefined && (
        <dl className="pop-in flex flex-col gap-2 rounded-xl bg-surface-2 p-3.5 text-sm">
          <div className="flex justify-between gap-3">
            <dt className="text-muted">In dollars</dt>
            <dd className="font-medium tabular-nums">{usd(budgetUsd)}</dd>
          </div>
          {data.median_price_usd_kg && (
            <div className="flex justify-between gap-3">
              <dt className="text-muted">At the median price</dt>
              <dd className="font-medium tabular-nums">
                ≈ {weight(budgetUsd / data.median_price_usd_kg)}
              </dd>
            </div>
          )}
          {cheapest && (
            <div className="flex justify-between gap-3">
              <dt className="text-muted">Most for your money</dt>
              <dd className="text-right font-medium tabular-nums">
                ≈ {weight(budgetUsd / cheapest.unit_price_usd_kg)}
                <span className="block text-xs font-normal text-muted">
                  from {cheapest.country.name}
                </span>
              </dd>
            </div>
          )}
        </dl>
      )}
      <RateNote currency={currency} />
    </Card>
  );
}

function CurrentSuppliers({ data }: { data: SourcingPage }) {
  const list = data.current_suppliers;
  return (
    <Card className="flex flex-col gap-4 p-5">
      <CardHeader
        icon={<Truck />}
        title={`Who supplies ${data.buyer.name} today`}
        description={`Share of ${data.buyer.name}’s ${data.product.name} imports, and the price paid.`}
      />
      {list.length === 0 ? (
        <p className="rounded-xl bg-surface-2 p-3.5 text-sm text-muted">
          {data.buyer.name} doesn’t import measurable amounts of {data.product.name} yet: you’d be
          opening a new route.
        </p>
      ) : (
        <ul className="flex flex-col gap-3">
          {list.map((c) => (
            <li key={c.country.code} className="flex flex-col gap-1.5">
              <span className="flex items-baseline justify-between gap-3 text-sm">
                <span className="truncate font-medium">{c.country.name}</span>
                <span className="shrink-0 text-muted tabular-nums">
                  <span className="font-medium text-fg">{percent(c.share, { floor: true })}</span>
                  {c.unit_price_usd_kg !== null && ` · ${perKg(c.unit_price_usd_kg)}`}
                </span>
              </span>
              <span aria-hidden className="relative h-1.5 rounded-full bg-surface-2">
                <span
                  className="grow-x absolute inset-y-0 left-0 rounded-full"
                  style={{ width: `${c.share * 100}%`, background: "var(--chart-exporter)" }}
                />
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/** Where to buy a product: picks, every supplier compared, budget, and what to do next. */
/** Makers to contact in one of the picked supplier countries (the best value first). */
function SupplierLeads({ data }: { data: SourcingPage }) {
  const countries = [
    ...new Map(
      [...data.picks.map((p) => p.country), ...data.suppliers.map((s) => s.country)].map((c) => [
        c.code,
        c,
      ]),
    ).values(),
  ].slice(0, 4);
  const [code, setCode] = useState(countries[0]?.code);
  const country = countries.find((c) => c.code === code) ?? countries[0];
  if (!country) return null;
  return (
    <div className="flex flex-col gap-3">
      {countries.length > 1 && (
        <Segmented
          label="Supplier country"
          value={country.code}
          onChange={setCode}
          items={countries.map((c) => ({ value: c.code, label: c.name }))}
        />
      )}
      <LeadsPanel
        key={country.code}
        hs6={data.product.hs6}
        country={country.code}
        countryName={country.name}
        productName={data.product.name}
        side="suppliers"
      />
      <FreightEstimate
        origin={country.code}
        dest={data.buyer.code}
        hs6={data.product.hs6}
        title={`Shipping from ${country.name}`}
      />
    </div>
  );
}

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

  if (profile.isPending || (buyer && page.isPending)) return <SourcingSkeleton />;
  if (!buyer) {
    return (
      <Page>
        <EmptyState
          icon={<MapPin />}
          title="Tell us where you’re based first"
          action={<ButtonLink href="/onboarding">Set up your business</ButtonLink>}
        >
          We compare suppliers and prices for buyers in your country.
        </EmptyState>
      </Page>
    );
  }
  if (page.isError || !page.data) {
    const missing = page.error instanceof ApiError && page.error.status === 404;
    return (
      <Page>
        <BackLink />
        <EmptyState
          icon={missing ? <PackageX /> : <RotateCcw />}
          title={missing ? "No supplier data for this product" : "Couldn’t load suppliers"}
          action={
            missing ? (
              <ButtonLink href="/app/buy">Search another product</ButtonLink>
            ) : (
              <Button variant="secondary" onClick={() => void page.refetch()}>
                <RotateCcw /> Try again
              </Button>
            )
          }
        >
          {missing ? page.error?.message : "Check your connection, then try again."}
        </EmptyState>
      </Page>
    );
  }

  const data = page.data;
  const budget = parseAmount(budgetText);
  const budgetUsd = budget !== null ? fx.toUsd(budget) : undefined;
  const priced = data.suppliers.filter(
    (s): s is SupplierOption & { unit_price_usd_kg: number } => s.unit_price_usd_kg !== null,
  );
  const option = (code: string) => data.suppliers.find((s) => s.country.code === code);
  const best = data.picks.find((p) => p.kind === "best_value") ?? data.picks[0];
  const askHref = `/app/ask?q=${encodeURIComponent(
    `How do I find verified ${data.product.name} exporters${
      best ? ` in ${best.country.name}` : ""
    } to buy from, for ${data.buyer.name}?`,
  )}`;

  return (
    <Page>
      <PageHeader
        eyebrow={<BackLink />}
        title={`Where to buy ${data.product.name}`}
        description={
          <>
            For buyers in <span className="font-medium text-fg">{data.buyer.name}</span>:{" "}
            {data.suppliers.length} supplier countries compared on price, momentum and reach.{" "}
            <span className="text-subtle">
              {shortProductName(data.product.description)} · HS {data.product.hs6}
            </span>
          </>
        }
        actions={
          <ButtonLink
            href={`/app/ask?q=${encodeURIComponent(`Where should I buy ${data.product.name} from, for ${data.buyer.name}?`)}`}
            variant="secondary"
          >
            <Sparkles /> Ask about this
          </ButtonLink>
        }
      />

      {data.picks.length > 0 && (
        <section aria-label="Our picks" className="rise-in" style={delay(60)}>
          <ul className="-mx-4 flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-1 sm:mx-0 sm:grid sm:grid-cols-2 sm:gap-4 sm:overflow-visible sm:px-0 sm:pb-0 lg:grid-cols-4">
            {data.picks.map((pick) => (
              <li key={pick.kind} className="w-[78%] shrink-0 snap-start sm:w-auto">
                <PickCard pick={pick} option={option(pick.country.code)} />
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <Card id="compare" className="rise-in overflow-hidden pt-5" style={delay(120)}>
          <div className="px-4 pb-3 sm:px-5">
            <CardHeader
              icon={<Scale />}
              title={`Every supplier of ${data.product.name}, compared`}
              description={
                data.median_price_usd_kg
                  ? `The median price is ${perKg(data.median_price_usd_kg)} (the dotted line). Cheaper isn’t always better: check quality with samples.`
                  : "Prices are averages over grades and qualities."
              }
            />
          </div>
          {data.suppliers.length > 0 ? (
            <SupplierTable
              suppliers={data.suppliers}
              median={data.median_price_usd_kg}
              budgetUsd={budgetUsd}
            />
          ) : (
            <p className="px-5 pb-5 text-sm text-muted">No supplier countries listed.</p>
          )}
        </Card>

        {/* Phones: budget above the comparison, today's suppliers below it. */}
        <div className="contents lg:sticky lg:top-20 lg:flex lg:flex-col lg:gap-4">
          <div className="order-first lg:order-none">
            <Budget
              data={data}
              budgetText={budgetText}
              setBudgetText={setBudgetText}
              currency={activeCurrency}
              setCurrency={setCurrency}
              home={home}
              budgetUsd={budgetUsd}
              priced={priced}
            />
          </div>
          <CurrentSuppliers data={data} />
        </div>
      </div>

      <section aria-label="Who to buy from" className="rise-in" style={delay(160)}>
        <SupplierLeads data={data} />
      </section>

      <Card className="rise-in p-5 sm:p-6" style={delay(200)}>
        <CardHeader
          icon={<ListChecks />}
          title="Your next steps"
          description={`From this page to your first order of ${data.product.name}. Tick them off as you go.`}
        />
        <div className="mt-5">
          <NextSteps id={`${data.buyer.code}-${data.product.hs6}`} askHref={askHref} />
        </div>
      </Card>

      <p className="text-xs text-subtle">
        Customs data {data.data_year} (CEPII BACI). Prices are export value ÷ weight across all
        buyers: an average over grades and qualities, not a quote. {capitalize(data.product.name)} =
        HS {data.product.hs6}.
      </p>
    </Page>
  );
}
