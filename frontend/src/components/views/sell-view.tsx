"use client";

import { ArrowRight, Compass, PackagePlus, TrendingUp } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { CSSProperties } from "react";

import { ProductPicker } from "@/components/markets/product-picker";
import { VerdictBadge } from "@/components/markets/verdict";
import { ButtonLink } from "@/components/ui/button";
import { Card, CardHeader, Page, PageHeader } from "@/components/ui/card";
import { EmptyState, Skeleton } from "@/components/ui/empty";
import { Problem } from "@/components/views/states";
import { useDashboard, useProfile } from "@/lib/api/queries";
import { capitalize, money, shortProductName, signedPercent } from "@/lib/format";

/** Selling: search any product, or jump into the user's own products' best markets. */
export function SellView() {
  const router = useRouter();
  const profile = useProfile();
  const sells = profile.data !== null && profile.data?.goal !== "buy";
  const dashboard = useDashboard(Boolean(profile.data) && sells);

  if (profile.isPending) {
    return (
      <Page>
        <Skeleton className="h-28" />
        <Skeleton className="h-64" />
      </Page>
    );
  }
  if (profile.isError)
    return <Problem title="Couldn’t load your products">Please refresh.</Problem>;
  const exporter = profile.data?.exporter;

  return (
    <Page>
      <PageHeader
        title="Where to sell"
        description={
          exporter
            ? `Markets ranked for exporters in ${exporter.name}: demand, competition, your position and size.`
            : "Pick your country in settings to see ranked markets."
        }
        actions={
          <ButtonLink href="/app/browse" variant="secondary">
            <Compass /> Explore niches
          </ButtonLink>
        }
      />

      <Card className="rise-in relative z-30 p-5 sm:p-6">
        <CardHeader
          icon={<TrendingUp />}
          title="Find markets for any product"
          description="Type it the way you’d say it: “cotton towels”, “basmati rice”, or an HS code."
        />
        <div className="mt-4 max-w-2xl">
          <ProductPicker
            exporter={exporter?.code}
            placeholder="What do you want to sell?"
            onSelect={(p) => router.push(`/app/markets/${p.hs6}`)}
          />
        </div>
      </Card>

      <section className="flex flex-col gap-4">
        <h2 className="text-lg font-semibold tracking-tight">Your products</h2>
        {dashboard.isPending && sells ? (
          <div className="grid gap-4 md:grid-cols-2">
            <Skeleton className="h-56" />
            <Skeleton className="h-56" />
          </div>
        ) : !dashboard.data?.products.length ? (
          <EmptyState
            icon={<PackagePlus />}
            title="No products yet"
            action={
              <ButtonLink href="/app/settings/business" variant="primary">
                Add products
              </ButtonLink>
            }
          >
            Add what you export and we’ll keep its best markets one click away.
          </EmptyState>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {dashboard.data.products.map((entry, i) => (
              <Card
                key={entry.product.hs6}
                className="rise-in flex flex-col gap-4 p-5"
                style={{ "--delay": `${i * 60}ms` } as CSSProperties}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="text-lg font-semibold">{capitalize(entry.product.name)}</h3>
                    <p className="truncate text-xs text-subtle" title={entry.product.description}>
                      {shortProductName(entry.product.description)} · HS {entry.product.hs6}
                    </p>
                  </div>
                  <span className="shrink-0 rounded-full bg-surface-2 px-2.5 py-1 text-xs text-muted">
                    {entry.total_markets} markets
                  </span>
                </div>
                <ul className="flex flex-col">
                  {entry.top.map((m) => (
                    <li key={m.market.code}>
                      <Link
                        href={`/app/markets/${entry.product.hs6}/${m.market.code}`}
                        className="flex items-center gap-3 rounded-xl px-2 py-2 transition-colors hover:bg-surface-2"
                      >
                        <span className="w-5 text-xs text-subtle tabular-nums">{m.rank}</span>
                        <span className="min-w-0 flex-1 truncate text-sm">{m.market.name}</span>
                        <span className="hidden text-xs text-muted tabular-nums sm:block">
                          {money(m.market_imports_usd)} · {signedPercent(m.import_growth_3y)}
                        </span>
                        <VerdictBadge verdict={m.verdict} />
                      </Link>
                    </li>
                  ))}
                </ul>
                <Link
                  href={`/app/markets/${entry.product.hs6}`}
                  className="mt-auto inline-flex items-center gap-1 text-sm font-medium text-brand hover:underline"
                >
                  See all {entry.total_markets} markets <ArrowRight className="h-4 w-4" />
                </Link>
              </Card>
            ))}
          </div>
        )}
      </section>
    </Page>
  );
}
