"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import type { CSSProperties } from "react";

import { Loading, Problem } from "@/components/views/states";
import { useNiches } from "@/lib/api/queries";
import { useExporter, withExporter } from "@/lib/use-exporter";

const delay = (ms: number) => ({ "--delay": `${ms}ms` }) as CSSProperties;

/** Product niches by sector; empty niches stay visible but quiet, so nothing feels hidden. */
export function BrowseView() {
  const override = useSearchParams().get("exporter");
  const exporter = useExporter();
  const niches = useNiches(exporter.code);

  if (exporter.pending || (exporter.code && niches.isPending)) return <Loading />;
  if (!exporter.code) {
    return (
      <Problem
        title="Pick your country first"
        action={{ href: "/onboarding", label: "Set up your markets →" }}
      />
    );
  }
  if (niches.isError || !niches.data) {
    return <Problem title="Couldn’t load niches">Please refresh the page.</Problem>;
  }

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-12 px-6 py-12">
      <div className="rise-in">
        <h1 className="text-3xl font-semibold tracking-tight">Browse by niche</h1>
        <p className="mt-2 text-sage">
          Pick a product group to see its products and the best market for each.
        </p>
      </div>

      {niches.data.map((sector, i) => (
        <section key={sector.name} className="rise-in" style={delay(80 + i * 100)}>
          <h2 className="text-lg font-semibold tracking-tight">{sector.name}</h2>
          <ul className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            {sector.niches.map((niche) => {
              const empty = niche.products === 0;
              return (
                <li key={niche.slug}>
                  {empty ? (
                    <div className="h-full rounded-xl border border-ink-line/60 p-4 opacity-60">
                      <p className="text-sm">{niche.name}</p>
                      <p className="mt-1 text-xs text-sage-dim">No ranked products</p>
                    </div>
                  ) : (
                    <Link
                      href={withExporter(`/app/browse/${niche.slug}`, override)}
                      className="block h-full rounded-xl border border-ink-line bg-ink-raised p-4 transition-all duration-200 hover:-translate-y-0.5 hover:border-sage-dim/60"
                    >
                      <p className="text-sm font-medium">{niche.name}</p>
                      <p className="mt-1 text-xs text-sage">
                        {niche.products} product{niche.products === 1 ? "" : "s"}
                      </p>
                    </Link>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </main>
  );
}
