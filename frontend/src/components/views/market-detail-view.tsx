"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { type CSSProperties, use } from "react";

import { BriefPanel } from "@/components/markets/brief-panel";
import { RecentPanel } from "@/components/markets/recent-panel";
import { SupplierChart } from "@/components/markets/supplier-chart";
import { HowWeDecide, SellingBadge, SignalGrid, VerdictPanel } from "@/components/markets/verdict";
import { PriceCheck } from "@/components/money/price-check";
import { DataNote, Loading, Problem } from "@/components/views/states";
import { ApiError, useMarketDetail } from "@/lib/api/queries";
import { money, percent, points, shortProductName, signedPercent } from "@/lib/format";
import { useExporter, withExporter } from "@/lib/use-exporter";

function StatTile({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-2xl border border-ink-line bg-ink-raised p-5">
      <p className="text-xs text-sage-dim">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      {note && <p className="mt-1 text-xs text-sage">{note}</p>}
    </div>
  );
}

/** One market in depth: the numbers, why it ranks here, and who supplies it. */
export function MarketDetailView({ params }: { params: Promise<{ hs6: string; market: string }> }) {
  const { hs6, market } = use(params);
  const override = useSearchParams().get("exporter");
  const exporter = useExporter();
  const detail = useMarketDetail(exporter.code, hs6, market.toUpperCase());
  const back = withExporter(`/app/markets/${hs6}`, override);

  if (exporter.pending || (exporter.code && detail.isPending)) return <Loading />;
  if (!exporter.code) {
    return (
      <Problem
        title="Pick your country first"
        action={{ href: "/onboarding", label: "Set up your markets →" }}
      />
    );
  }
  if (detail.isError) {
    const missing = detail.error instanceof ApiError && detail.error.status === 404;
    return (
      <Problem
        title={missing ? "Not a ranked market" : "Couldn’t load this market"}
        action={{ href: back, label: "Back to the ranking" }}
      >
        {missing ? detail.error.message : "Please refresh the page."}
      </Problem>
    );
  }

  if (!detail.data) return <Loading />;

  const { exporter: exp, product, data, market: m, suppliers } = detail.data;
  const rival = m.top_rival;

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-8 px-6 py-12">
      <div className="rise-in">
        <Link href={back} className="text-sm text-sage hover:text-cream">
          ← All markets for {product.name}
        </Link>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{m.market.name}</h1>
          {m.already_selling && <SellingBadge />}
        </div>
        <p className="mt-2 text-sage">
          Ranked #{m.rank} for {product.name} from {exp.name} · opportunity score: {m.label}
        </p>
      </div>

      <section
        className="rise-in rounded-2xl border border-ink-line bg-ink-raised p-6"
        style={{ "--delay": "60ms" } as CSSProperties}
      >
        <VerdictPanel verdict={m.verdict} />
      </section>

      <div
        className="rise-in grid grid-cols-2 gap-4 md:grid-cols-4"
        style={{ "--delay": "100ms" } as CSSProperties}
      >
        <StatTile label={`Market size, ${data.end_year}`} value={money(m.market_imports_usd)} />
        <StatTile
          label="Import growth / yr"
          value={signedPercent(m.import_growth_3y)}
          note={`${data.start_year}–${data.end_year}`}
        />
        <StatTile
          label={`${exp.name}'s share`}
          value={percent(m.exporter_share, { floor: true })}
        />
        <StatTile
          label="Main rival"
          value={rival ? rival.name : "None"}
          note={
            rival && m.top_rival_share_change !== null
              ? `${points(m.top_rival_share_change)} since ${data.start_year}`
              : undefined
          }
        />
      </div>

      <div className="rise-in" style={{ "--delay": "140ms" } as CSSProperties}>
        <BriefPanel exporter={exp.code} hs6={product.hs6} market={m.market.code} />
      </div>

      <section
        className="rise-in rounded-2xl border border-ink-line bg-ink-raised p-6"
        style={{ "--delay": "180ms" } as CSSProperties}
      >
        <h2 className="text-lg font-medium">The signals behind it</h2>
        <div className="mt-4">
          <SignalGrid signals={m.signals} />
        </div>
      </section>

      <div className="rise-in" style={{ "--delay": "220ms" } as CSSProperties}>
        <PriceCheck
          exporter={exp.code}
          market={m.market.code}
          marketName={m.market.name}
          averagePrice={m.market_unit_price_usd_kg ?? null}
          suppliers={suppliers}
        />
      </div>

      {suppliers.length > 0 && (
        <div className="rise-in" style={{ "--delay": "260ms" } as CSSProperties}>
          <SupplierChart
            suppliers={suppliers}
            startYear={data.start_year}
            endYear={data.end_year}
            highlight={exp.code}
          />
        </div>
      )}

      <div className="rise-in" style={{ "--delay": "340ms" } as CSSProperties}>
        <RecentPanel
          exporter={exp.code}
          exporterName={exp.name}
          hs6={product.hs6}
          market={m.market.code}
          annualEndYear={data.end_year}
        />
      </div>

      <HowWeDecide />
      <DataNote start={data.start_year} end={data.end_year} />
    </main>
  );
}
