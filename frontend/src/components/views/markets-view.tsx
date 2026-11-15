"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { use } from "react";

import { MarketCard } from "@/components/markets/market-card";
import { Button } from "@/components/ui/button";
import { DataNote, Loading, Problem } from "@/components/views/states";
import { ApiError, useMarkets } from "@/lib/api/queries";
import { shortProductName } from "@/lib/format";
import { useExporter, withExporter } from "@/lib/use-exporter";

/** Every ranked market for one product, loaded a page at a time. */
export function MarketsView({ params }: { params: Promise<{ hs6: string }> }) {
  const { hs6 } = use(params);
  const override = useSearchParams().get("exporter");
  const exporter = useExporter();
  const markets = useMarkets(exporter.code, hs6);

  if (exporter.pending || (exporter.code && markets.isPending)) return <Loading />;
  if (!exporter.code) {
    return (
      <Problem
        title="Pick your country first"
        action={{ href: "/onboarding", label: "Set up your markets →" }}
      >
        Rankings are built for exporters in a specific country.
      </Problem>
    );
  }
  if (markets.isError) {
    const missing = markets.error instanceof ApiError && markets.error.status === 404;
    return (
      <Problem
        title={missing ? "Nothing to show" : "Couldn’t load markets"}
        action={{ href: "/app", label: "Back to dashboard" }}
      >
        {missing ? markets.error.message : "Please refresh the page."}
      </Problem>
    );
  }

  if (!markets.data) return <Loading />;

  const first = markets.data.pages[0];
  const items = markets.data.pages.flatMap((page) => page.items);

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-8 px-6 py-12">
      <div className="rise-in">
        <Link href="/app" className="text-sm text-sage hover:text-cream">
          ← Dashboard
        </Link>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight">
          {shortProductName(first.product.description)}
        </h1>
        <p className="mt-2 text-sage">
          {first.total} markets ranked for exporters from {first.exporter.name} · HS {hs6}
        </p>
      </div>

      {items.length === 0 ? (
        <Problem title="No ranked markets yet">
          No market for this product passed the filters (at least $10M of imports and a competitive
          edge for {first.exporter.name}).
        </Problem>
      ) : (
        <div className="flex flex-col gap-4">
          {items.map((item) => (
            <MarketCard
              key={item.market.code}
              item={item}
              href={withExporter(`/app/markets/${hs6}/${item.market.code}`, override)}
            />
          ))}
        </div>
      )}

      {markets.hasNextPage && (
        <div className="flex justify-center">
          <Button
            variant="secondary"
            disabled={markets.isFetchingNextPage}
            onClick={() => markets.fetchNextPage()}
          >
            {markets.isFetchingNextPage ? "Loading…" : "Show more markets"}
          </Button>
        </div>
      )}

      {first.data && <DataNote start={first.data.start_year} end={first.data.end_year} />}
    </main>
  );
}
