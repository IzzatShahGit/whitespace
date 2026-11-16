"use client";

import {
  ArrowRight,
  MapPin,
  PackagePlus,
  PackageSearch,
  RotateCcw,
  Scale,
  Search,
  Settings2,
  Wallet,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { CSSProperties } from "react";

import { PICK } from "@/components/buy/picks";
import { ProductPicker } from "@/components/markets/product-picker";
import { Button, ButtonLink } from "@/components/ui/button";
import { Card, CardHeader, Page, PageHeader } from "@/components/ui/card";
import { EmptyState, Skeleton } from "@/components/ui/empty";
import { type Product, type SourcingPick, useMe, useProfile, useSourcing } from "@/lib/api/queries";
import { capitalize, shortProductName } from "@/lib/format";
import { perKg } from "@/lib/money";

const delay = (ms: number) => ({ "--delay": `${ms}ms` }) as CSSProperties;

function greeting(now = new Date()): string {
  const hour = now.getHours();
  return hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
}

function PickLine({ pick, price }: { pick: SourcingPick; price?: number | null }) {
  const { icon: Icon, short } = PICK[pick.kind];
  return (
    <div className="flex items-center gap-2.5 text-sm">
      <Icon aria-hidden className="h-4 w-4 shrink-0 text-subtle" />
      <dt className="text-muted">{short}</dt>
      <dd className="ml-auto truncate text-right font-medium">
        {pick.country.name}
        {price != null && (
          <span className="font-normal text-muted tabular-nums"> · {perKg(price)}</span>
        )}
      </dd>
    </div>
  );
}

/** One of the user's products: the picks at a glance, the whole card opens the comparison. */
function ProductCard({
  buyer,
  product,
  index,
}: {
  buyer: string;
  product: Product;
  index: number;
}) {
  const page = useSourcing(buyer, product.hs6);
  const data = page.data;
  const price = (code: string) =>
    data?.suppliers.find((s) => s.country.code === code)?.unit_price_usd_kg;
  const picks = (data?.picks ?? []).filter((p) => p.kind !== "current").slice(0, 3);

  return (
    <Link
      href={`/app/buy/${product.hs6}`}
      className="rise-in group flex h-full flex-col gap-4 rounded-2xl border border-line bg-surface p-5 shadow-card transition-colors duration-150 hover:border-line-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
      style={delay(100 + index * 40)}
    >
      <div className="min-w-0">
        <h3 className="text-lg font-semibold tracking-tight">{capitalize(product.name)}</h3>
        <p className="truncate text-xs text-subtle" title={product.description}>
          {shortProductName(product.description)} · HS {product.hs6}
        </p>
      </div>
      {page.isPending ? (
        <div className="flex flex-col gap-2.5" aria-label="Comparing suppliers">
          <Skeleton className="h-5" />
          <Skeleton className="h-5" />
          <Skeleton className="h-5" />
        </div>
      ) : page.isError || !data ? (
        <p className="text-sm text-muted">No supplier data for this product yet.</p>
      ) : (
        <dl className="flex flex-col gap-2.5">
          {picks.map((pick) => (
            <PickLine key={pick.kind} pick={pick} price={price(pick.country.code)} />
          ))}
          {data.median_price_usd_kg && (
            <div className="flex items-center gap-2.5 border-t border-line pt-2.5 text-sm">
              <Scale aria-hidden className="h-4 w-4 shrink-0 text-subtle" />
              <dt className="text-muted">Median price</dt>
              <dd className="ml-auto font-medium tabular-nums">
                {perKg(data.median_price_usd_kg)}
              </dd>
            </div>
          )}
        </dl>
      )}
      <span className="mt-auto inline-flex items-center gap-1 text-sm font-medium text-brand">
        Compare {data ? `${data.suppliers.length} ` : ""}suppliers
        <ArrowRight className="h-4 w-4 transition-transform duration-150 group-hover:translate-x-0.5" />
      </span>
    </Link>
  );
}

const HOW = [
  {
    icon: Search,
    title: "Search",
    text: "Type what you buy in everyday words, or an HS code.",
  },
  {
    icon: Scale,
    title: "Compare",
    text: "Each country’s price per kg, momentum and reach, from customs data.",
  },
  {
    icon: Wallet,
    title: "Budget",
    text: "Enter a budget in rupees, taka or dollars to see how much it buys where.",
  },
];

function HowItWorks() {
  return (
    <ol className="grid gap-3 sm:grid-cols-3 sm:gap-4">
      {HOW.map(({ icon: Icon, title, text }, i) => (
        <li key={title} className="flex gap-3.5 rounded-2xl border border-line bg-surface/60 p-4">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-soft text-brand">
            <Icon className="h-5 w-5" aria-hidden />
          </span>
          <span>
            <span className="block text-xs font-medium text-subtle">Step {i + 1}</span>
            <span className="block text-sm font-medium">{title}</span>
            <span className="mt-0.5 block text-sm leading-6 text-muted">{text}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}

/** Buying home (also Home for buy-only users): search any product, then your own products. */
export function BuyView() {
  const router = useRouter();
  const onHome = usePathname() === "/app";
  const me = useMe();
  const profile = useProfile();

  if (profile.isPending) {
    return (
      <Page aria-busy>
        <Skeleton className="h-16 w-full max-w-md" />
        <Skeleton className="h-36 rounded-2xl" />
        <div className="grid gap-4 md:grid-cols-3">
          <Skeleton className="h-60 rounded-2xl" />
          <Skeleton className="h-60 rounded-2xl" />
          <Skeleton className="h-60 rounded-2xl" />
        </div>
      </Page>
    );
  }
  if (profile.isError) {
    return (
      <Page>
        <EmptyState
          icon={<RotateCcw />}
          title="Couldn’t load your products"
          action={
            <Button variant="secondary" onClick={() => void profile.refetch()}>
              Try again
            </Button>
          }
        >
          Check your connection, then try again.
        </EmptyState>
      </Page>
    );
  }
  const p = profile.data;
  if (!p) {
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
  const firstName = me.data?.full_name.split(" ")[0];
  const buys = p.goal !== "sell";

  return (
    <Page>
      <PageHeader
        eyebrow={onHome ? `Buying into ${p.exporter.name}` : undefined}
        title={onHome ? `${greeting()}${firstName ? `, ${firstName}` : ""}` : "Where to buy"}
        description={`Compare the countries that make what you need, priced per kg, for buyers in ${p.exporter.name}.`}
        actions={
          buys ? (
            <ButtonLink href="/app/settings/business" variant="secondary">
              <Settings2 /> Edit products
            </ButtonLink>
          ) : undefined
        }
      />

      <Card className="rise-in relative z-30 p-5 sm:p-6" style={delay(40)}>
        <CardHeader
          icon={<PackageSearch />}
          title="Find suppliers for any product"
          description="Type it the way you’d say it: “cotton yarn”, “solar panels”, or an HS code."
        />
        <div className="mt-4 max-w-2xl">
          <ProductPicker
            mode="buy"
            exporter={p.exporter.code}
            label="Search a product to buy"
            placeholder="What do you want to buy?"
            onSelect={(product) => router.push(`/app/buy/${product.hs6}`)}
          />
        </div>
      </Card>

      {buys ? (
        <section className="flex flex-col gap-4" aria-labelledby="your-products">
          <div className="flex items-baseline justify-between gap-3">
            <h2 id="your-products" className="text-lg font-semibold tracking-tight">
              Your products
            </h2>
            <span className="text-sm text-muted">Best places to buy each</span>
          </div>
          {p.products.length > 0 ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {p.products.map((product, i) => (
                <ProductCard
                  key={product.hs6}
                  buyer={p.exporter.code}
                  product={product}
                  index={i}
                />
              ))}
            </div>
          ) : (
            <EmptyState
              icon={<PackagePlus />}
              title="No products yet"
              action={<ButtonLink href="/app/settings/business">Add products</ButtonLink>}
            >
              Add what you buy and we’ll keep its best suppliers one click away.
            </EmptyState>
          )}
        </section>
      ) : (
        <section className="rise-in flex flex-col gap-4" style={delay(80)} aria-labelledby="how">
          <div>
            <h2 id="how" className="text-lg font-semibold tracking-tight">
              How buying works
            </h2>
            <p className="mt-1 text-sm text-muted">
              Do you also import?{" "}
              <Link href="/app/settings/business" className="text-brand hover:underline">
                Choose “Both” in your business settings
              </Link>{" "}
              to keep your inputs here.
            </p>
          </div>
          <HowItWorks />
        </section>
      )}
    </Page>
  );
}
