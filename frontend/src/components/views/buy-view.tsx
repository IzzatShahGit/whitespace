"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { CSSProperties } from "react";

import { ProductPicker } from "@/components/markets/product-picker";
import { Loading, Problem } from "@/components/views/states";
import { type Product, useMe, useProfile, useSourcing } from "@/lib/api/queries";
import { capitalize, shortProductName } from "@/lib/format";
import { perKg } from "@/lib/money";

const delay = (ms: number) => ({ "--delay": `${ms}ms` }) as CSSProperties;

/** One of the user's products: the best-value pick at a glance. */
function ProductCard({ buyer, product }: { buyer: string; product: Product }) {
  const page = useSourcing(buyer, product.hs6);
  // Niche products may have no cheap supplier big enough to pick; fall back to the safest.
  const best =
    page.data?.picks.find((p) => p.kind === "best_value") ??
    page.data?.picks.find((p) => p.kind === "most_established");
  const rising = page.data?.picks.find((p) => p.kind === "rising");
  return (
    <Link
      href={`/app/buy/${product.hs6}`}
      className="group flex h-full flex-col gap-3 rounded-2xl border border-ink-line bg-ink-raised p-5 transition-all duration-200 hover:-translate-y-0.5 hover:border-ember/60"
    >
      <h3 className="font-medium">{capitalize(product.name)}</h3>
      <p className="line-clamp-2 text-xs text-sage-dim" title={product.description}>
        {shortProductName(product.description)} · HS {product.hs6}
      </p>
      {page.isPending && <p className="text-sm text-sage-dim">Comparing suppliers…</p>}
      {page.isError && <p className="text-sm text-sage-dim">No supplier data yet.</p>}
      {page.data && (
        <dl className="mt-auto flex flex-col gap-1.5 text-sm">
          {best && (
            <div className="flex justify-between gap-3">
              <dt className="text-sage">{best.title}</dt>
              <dd className="text-ember">{best.country.name}</dd>
            </div>
          )}
          {rising && (
            <div className="flex justify-between gap-3">
              <dt className="text-sage">Rising</dt>
              <dd>{rising.country.name}</dd>
            </div>
          )}
          {page.data.median_price_usd_kg && (
            <div className="flex justify-between gap-3">
              <dt className="text-sage">Median price</dt>
              <dd className="tabular-nums">{perKg(page.data.median_price_usd_kg)}</dd>
            </div>
          )}
        </dl>
      )}
      <span className="text-xs text-sage group-hover:text-cream">
        See all {page.data?.suppliers.length ?? ""} suppliers →
      </span>
    </Link>
  );
}

const HOW = [
  ["Search", "Type what you buy in everyday words, or an HS code."],
  ["Compare", "See each country’s price per kg, reliability and momentum, from customs data."],
  ["Budget", "Enter your budget in rupees, taka or dollars to see how much it buys where."],
] as const;

/** Buying home: search any product; the user's own products if they buy. */
export function BuyView() {
  const router = useRouter();
  const me = useMe();
  const profile = useProfile();

  if (profile.isPending) return <Loading />;
  if (profile.isError) return <Problem title="Couldn’t load your preferences" />;
  const p = profile.data;
  if (!p) {
    return (
      <Problem
        title="Tell us where you’re based first"
        action={{ href: "/onboarding", label: "Set up your preferences →" }}
      />
    );
  }
  const firstName = me.data?.full_name.split(" ")[0];
  const buys = p.goal !== "sell";

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-12 px-6 py-12">
      <section className="rise-in relative z-30 flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
            {firstName ? `${firstName}, find` : "Find"} the best place to buy
          </h1>
          <p className="mt-2 text-sage">
            Compare the countries that make what you need, priced per kg, for buyers in{" "}
            {p.exporter.name}.
          </p>
        </div>
        <div className="max-w-2xl">
          <ProductPicker
            mode="buy"
            exporter={p.exporter.code}
            placeholder="What do you want to buy? e.g. cotton yarn, solar panels"
            onSelect={(product) => router.push(`/app/buy/${product.hs6}`)}
          />
        </div>
      </section>

      {buys && p.products.length > 0 ? (
        <section className="rise-in flex flex-col gap-4" style={delay(80)}>
          <h2 className="text-xl font-semibold tracking-tight">Your products</h2>
          <div className="grid gap-4 md:grid-cols-3">
            {p.products.map((product) => (
              <ProductCard key={product.hs6} buyer={p.exporter.code} product={product} />
            ))}
          </div>
        </section>
      ) : (
        <section className="rise-in grid gap-4 md:grid-cols-3" style={delay(80)}>
          {HOW.map(([title, text], i) => (
            <div key={title} className="rounded-2xl border border-ink-line p-5">
              <p className="text-xs font-medium text-ember">Step {i + 1}</p>
              <h2 className="mt-1 font-medium">{title}</h2>
              <p className="mt-1 text-sm leading-6 text-sage">{text}</p>
            </div>
          ))}
        </section>
      )}
    </main>
  );
}
