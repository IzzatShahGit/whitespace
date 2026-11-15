"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { use } from "react";

import { LabelPill } from "@/components/markets/label-pill";
import { Loading, Problem } from "@/components/views/states";
import { ApiError, useNiche } from "@/lib/api/queries";
import { money, signedPercent, shortProductName } from "@/lib/format";
import { useExporter, withExporter } from "@/lib/use-exporter";

/** One niche: its products for this exporter, each with its best market. */
export function NicheView({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const override = useSearchParams().get("exporter");
  const exporter = useExporter();
  const niche = useNiche(exporter.code, slug);
  const back = withExporter("/app/browse", override);

  if (exporter.pending || (exporter.code && niche.isPending)) return <Loading />;
  if (!exporter.code) {
    return (
      <Problem
        title="Pick your country first"
        action={{ href: "/onboarding", label: "Set up your markets →" }}
      />
    );
  }
  if (niche.isError || !niche.data) {
    const missing = niche.error instanceof ApiError && niche.error.status === 404;
    return (
      <Problem
        title={missing ? "Niche not found" : "Couldn’t load this niche"}
        action={{ href: back, label: "Back to all niches" }}
      />
    );
  }

  const { name, sector, exporter: exp, products } = niche.data;
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-8 px-6 py-12">
      <div className="rise-in">
        <Link href={back} className="text-sm text-sage hover:text-cream">
          ← {sector}
        </Link>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight">{name}</h1>
        <p className="mt-2 text-sage">
          {products.length} product{products.length === 1 ? "" : "s"} with ranked markets for
          exporters from {exp.name}, strongest opportunity first.
        </p>
      </div>

      {products.length === 0 ? (
        <Problem title="No ranked products in this niche">
          None of its products passed the filters for {exp.name}.
        </Problem>
      ) : (
        <ul className="flex flex-col gap-3">
          {products.map(({ product, markets, best }) => (
            <li key={product.hs6}>
              <Link
                href={withExporter(`/app/markets/${product.hs6}`, override)}
                className="group block rounded-2xl border border-ink-line bg-ink-raised p-5 transition-all duration-200 hover:-translate-y-0.5 hover:border-sage-dim/60"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="font-medium">{shortProductName(product.description)}</p>
                    <p className="mt-0.5 text-xs text-sage-dim">
                      HS {product.hs6} · {markets} ranked markets
                    </p>
                  </div>
                  <span className="shrink-0 text-sm text-sage-dim transition-colors group-hover:text-cream">
                    All markets →
                  </span>
                </div>
                <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
                  <span className="text-sage-dim">Best market</span>
                  <span className="font-medium">{best.market.name}</span>
                  <LabelPill label={best.label} />
                  <span className="text-sage tabular-nums">
                    {money(best.market_imports_usd)} · {signedPercent(best.import_growth_3y)} / yr
                  </span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
