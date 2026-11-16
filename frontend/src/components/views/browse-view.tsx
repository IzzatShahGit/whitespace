"use client";

import { ChevronRight, MapPin, RotateCcw, Search, SearchX } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { type CSSProperties, useState } from "react";

import { nicheIcon, sectorIcon } from "@/components/browse/niche-icons";
import { Button, ButtonLink } from "@/components/ui/button";
import { Page, PageHeader } from "@/components/ui/card";
import { EmptyState, Skeleton } from "@/components/ui/empty";
import { inputClass } from "@/components/ui/field";
import { useNiches, useProfile } from "@/lib/api/queries";
import { useExporter, withExporter } from "@/lib/use-exporter";

const delay = (ms: number) => ({ "--delay": `${ms}ms` }) as CSSProperties;

function BrowseSkeleton() {
  return (
    <Page aria-busy>
      <div className="flex flex-col gap-3">
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-5 w-full max-w-lg" />
      </div>
      <Skeleton className="h-11 w-full max-w-md" />
      {[0, 1].map((s) => (
        <div key={s} className="flex flex-col gap-4">
          <Skeleton className="h-6 w-48" />
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
            {Array.from({ length: 8 }, (_, i) => (
              <Skeleton key={i} className="h-[4.5rem] rounded-2xl" />
            ))}
          </div>
        </div>
      ))}
    </Page>
  );
}

/** Product niches by sector, as an iconed grid; empty niches stay visible but quiet. */
export function BrowseView() {
  const override = useSearchParams().get("exporter");
  const exporter = useExporter();
  const niches = useNiches(exporter.code);
  const [filter, setFilter] = useState("");
  const profileName = useProfile().data?.exporter.name;

  if (exporter.pending || (exporter.code && niches.isPending)) return <BrowseSkeleton />;
  if (!exporter.code) {
    return (
      <Page>
        <EmptyState
          icon={<MapPin />}
          title="Pick your country first"
          action={<ButtonLink href="/onboarding">Set up your business</ButtonLink>}
        >
          Niches are ranked for exporters in your country.
        </EmptyState>
      </Page>
    );
  }
  if (niches.isError || !niches.data) {
    return (
      <Page>
        <EmptyState
          icon={<RotateCcw />}
          title="Couldn’t load niches"
          action={
            <Button variant="secondary" onClick={() => void niches.refetch()}>
              Try again
            </Button>
          }
        >
          Check your connection, then try again.
        </EmptyState>
      </Page>
    );
  }

  const needle = filter.trim().toLowerCase();
  const sectors = niches.data
    .map((s) => ({
      ...s,
      niches: s.niches.filter(
        (n) =>
          !needle || n.name.toLowerCase().includes(needle) || s.name.toLowerCase().includes(needle),
      ),
    }))
    .filter((s) => s.niches.length > 0);
  const profile = profileName && !override ? profileName : override?.toUpperCase();

  return (
    <Page>
      <PageHeader
        title="Explore niches"
        description={`Product groups with ranked markets for exporters in ${profile ?? "your country"}. Open one to see its products and the best market for each.`}
      />

      <div className="rise-in relative max-w-md" style={delay(40)}>
        <label htmlFor="niche-filter" className="sr-only">
          Find a niche
        </label>
        <Search
          aria-hidden
          className="pointer-events-none absolute top-1/2 left-4 h-[18px] w-[18px] -translate-y-1/2 text-subtle"
        />
        <input
          id="niche-filter"
          type="search"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Find a niche, e.g. rice or towels"
          className={`${inputClass} pl-11`}
        />
      </div>

      {sectors.length === 0 && (
        <EmptyState
          icon={<SearchX />}
          title={`No niche matches “${filter.trim()}”`}
          action={
            <Button variant="secondary" onClick={() => setFilter("")}>
              Show all niches
            </Button>
          }
        >
          Try a broader word, or search any product with ⌘K.
        </EmptyState>
      )}

      {sectors.map((sector, i) => {
        const SectorIcon = sectorIcon(sector.name);
        const products = sector.niches.reduce((sum, n) => sum + n.products, 0);
        return (
          <section
            key={sector.name}
            aria-labelledby={`sector-${i}`}
            className="rise-in flex flex-col gap-4"
            style={delay(Math.min(80 + i * 40, 240))}
          >
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-soft text-brand">
                <SectorIcon aria-hidden className="h-[18px] w-[18px]" />
              </span>
              <div>
                <h2 id={`sector-${i}`} className="text-lg font-semibold tracking-tight">
                  {sector.name}
                </h2>
                <p className="text-xs text-muted tabular-nums">
                  {sector.niches.length} niche{sector.niches.length === 1 ? "" : "s"} · {products}{" "}
                  ranked products
                </p>
              </div>
            </div>
            <ul className="grid grid-cols-1 gap-2.5 min-[420px]:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
              {sector.niches.map((niche) => {
                const Icon = nicheIcon(niche.slug, sector.name);
                const empty = niche.products === 0;
                const body = (
                  <>
                    <span
                      aria-hidden
                      className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${
                        empty ? "bg-surface-2 text-subtle" : "bg-surface-2 text-brand"
                      }`}
                    >
                      <Icon className="h-5 w-5" strokeWidth={1.75} />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">{niche.name}</span>
                      <span className="block text-xs text-muted tabular-nums">
                        {empty
                          ? "No ranked products yet"
                          : `${niche.products} product${niche.products === 1 ? "" : "s"}`}
                      </span>
                    </span>
                  </>
                );
                return (
                  <li key={niche.slug}>
                    {empty ? (
                      <div className="flex h-full items-center gap-3 rounded-2xl border border-dashed border-line p-3 text-muted">
                        {body}
                      </div>
                    ) : (
                      <Link
                        href={withExporter(`/app/browse/${niche.slug}`, override)}
                        className="group flex h-full items-center gap-3 rounded-2xl border border-line bg-surface p-3 shadow-card transition-colors duration-150 hover:border-line-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                      >
                        {body}
                        <ChevronRight
                          aria-hidden
                          className="h-4 w-4 shrink-0 text-subtle transition-transform duration-150 group-hover:translate-x-0.5"
                        />
                      </Link>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
    </Page>
  );
}
