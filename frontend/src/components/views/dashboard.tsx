"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type CSSProperties, useEffect } from "react";

import { MarketCard } from "@/components/markets/market-card";
import { ProductPicker } from "@/components/markets/product-picker";
import { HowWeDecide, VerdictBadge } from "@/components/markets/verdict";
import { buttonClass } from "@/components/ui/button";
import { DataNote, Loading, Problem } from "@/components/views/states";
import { useDashboard, useMe, useProfile } from "@/lib/api/queries";
import { shortProductName } from "@/lib/format";

const delay = (ms: number) => ({ "--delay": `${ms}ms` }) as CSSProperties;

export function Dashboard() {
  const router = useRouter();
  const me = useMe();
  const profile = useProfile();
  const dashboard = useDashboard(Boolean(profile.data));
  const needsOnboarding = profile.isSuccess && profile.data === null;

  useEffect(() => {
    if (needsOnboarding) router.replace("/onboarding");
  }, [needsOnboarding, router]);

  if (profile.isPending || needsOnboarding || dashboard.isPending) return <Loading />;
  if (profile.isError || dashboard.isError) {
    return <Problem title="Couldn’t load your dashboard">Please refresh the page.</Problem>;
  }

  const { profile: p, products, data, best_moves: bestMoves } = dashboard.data;
  const firstName = me.data?.full_name.split(" ")[0];

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-12 px-6 py-12">
      <section className="rise-in relative z-30 flex flex-col gap-6">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">
            {firstName ? `Hi ${firstName}, here` : "Here"}’s where to sell next
          </h1>
          <p className="mt-2 text-sage">
            The best new markets for your products, exporting from {p.exporter.name}.
          </p>
        </div>
        <div className="flex max-w-2xl flex-col gap-3 sm:flex-row sm:items-center">
          <div className="flex-1">
            <ProductPicker
              exporter={p.exporter.code}
              placeholder="Explore another product, e.g. basmati rice"
              onSelect={(product) => router.push(`/app/markets/${product.hs6}`)}
            />
          </div>
          <Link href="/app/browse" className={buttonClass("secondary", "h-12 shrink-0")}>
            Browse by niche
          </Link>
        </div>
      </section>

      {bestMoves.length > 0 && (
        <section className="rise-in flex flex-col gap-4" style={delay(80)}>
          <div>
            <h2 className="text-xl font-semibold tracking-tight">Your best moves</h2>
            <p className="text-sm text-sage">
              The strongest new markets across your products, where the data says go.
            </p>
          </div>
          <ol className="grid gap-4 md:grid-cols-3">
            {bestMoves.map(({ product, market }) => (
              <li key={`${product.hs6}-${market.market.code}`}>
                <Link
                  href={`/app/markets/${product.hs6}/${market.market.code}`}
                  className="group flex h-full flex-col gap-3 rounded-2xl border border-ember/30 bg-ink-raised p-5 transition-all duration-200 hover:-translate-y-0.5 hover:border-ember/60"
                >
                  <p className="text-xs text-sage-dim">{shortProductName(product.description)}</p>
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="text-lg font-medium">{market.market.name}</h3>
                    <VerdictBadge verdict={market.verdict} />
                  </div>
                  <p className="text-sm leading-6 text-sage">{market.verdict.summary}</p>
                  <p className="mt-auto text-xs text-sage">
                    <span className="text-cream">Next: </span>
                    {market.verdict.next_step}
                  </p>
                </Link>
              </li>
            ))}
          </ol>
        </section>
      )}

      {products.map((entry, i) => (
        <section
          key={entry.product.hs6}
          className="rise-in flex flex-col gap-4"
          style={delay(160 + i * 120)}
        >
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold tracking-tight">
                {shortProductName(entry.product.description)}
              </h2>
              <p className="text-sm text-sage-dim">
                HS {entry.product.hs6} · {entry.total_markets} ranked markets
              </p>
            </div>
            <Link
              href={`/app/markets/${entry.product.hs6}`}
              className="text-sm text-sage underline-offset-4 hover:text-cream hover:underline"
            >
              See all {entry.total_markets} markets →
            </Link>
          </div>
          {entry.top.length > 0 ? (
            <div className="grid gap-4 md:grid-cols-3">
              {entry.top.map((item) => (
                <MarketCard
                  key={item.market.code}
                  item={item}
                  compact
                  href={`/app/markets/${entry.product.hs6}/${item.market.code}`}
                />
              ))}
            </div>
          ) : (
            <p className="rounded-2xl border border-ink-line p-5 text-sm text-sage">
              You already sell to every ranked market for this product.
            </p>
          )}
        </section>
      ))}

      <HowWeDecide />
      {data && <DataNote start={data.start_year} end={data.end_year} />}
    </main>
  );
}
