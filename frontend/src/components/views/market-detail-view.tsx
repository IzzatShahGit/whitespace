"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { type CSSProperties, use } from "react";

import { LabelPill, SellingBadge } from "@/components/markets/label-pill";
import { RecentPanel } from "@/components/markets/recent-panel";
import { SupplierChart } from "@/components/markets/supplier-chart";
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
          ← All markets for {shortProductName(product.description)}
        </Link>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-semibold tracking-tight">{m.market.name}</h1>
          <LabelPill label={m.label} />
          {m.already_selling && <SellingBadge />}
        </div>
        <p className="mt-2 text-sage">
          Ranked #{m.rank} for {shortProductName(product.description).toLowerCase()} from {exp.name}
        </p>
      </div>

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

      <section
        className="rise-in rounded-2xl border border-ink-line bg-ink-raised p-6"
        style={{ "--delay": "180ms" } as CSSProperties}
      >
        <h2 className="text-lg font-medium">Why it ranks here</h2>
        <ul className="mt-4 flex flex-col gap-2.5">
          {m.reasons.map((reason) => (
            <li key={reason} className="flex items-start gap-2.5 text-sage">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rotate-45 bg-ember" aria-hidden />
              {reason}
            </li>
          ))}
        </ul>
      </section>

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

      <DataNote start={data.start_year} end={data.end_year} />
    </main>
  );
}
