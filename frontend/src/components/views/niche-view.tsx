"use client";

import {
  ArrowLeft,
  ArrowRight,
  ChevronRight,
  MapPin,
  PackageX,
  RotateCcw,
  Trophy,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { type CSSProperties, use, useState } from "react";

import { NicheIcon } from "@/components/browse/niche-icons";
import { VERDICT_TONE, VerdictBadge } from "@/components/markets/verdict";
import { Button, ButtonLink } from "@/components/ui/button";
import { Card, Page, PageHeader } from "@/components/ui/card";
import { EmptyState, Skeleton } from "@/components/ui/empty";
import { Segmented } from "@/components/ui/segmented";
import { ApiError, type NicheDetail, useNiche } from "@/lib/api/queries";
import { capitalize, money, shortProductName, signedPercent } from "@/lib/format";
import { useExporter, withExporter } from "@/lib/use-exporter";

const delay = (ms: number) => ({ "--delay": `${ms}ms` }) as CSSProperties;
const PAGE = 20;

type Tone = "all" | "positive" | "caution" | "negative";
const FILTERS: { value: Tone; label: string }[] = [
  { value: "all", label: "All" },
  { value: "positive", label: "Go / grow" },
  { value: "caution", label: "Test / defend" },
  { value: "negative", label: "Take care" },
];

type Item = NicheDetail["products"][number];

function Row({ item, href, rank }: { item: Item; href: string; rank: number }) {
  const { product, best, markets } = item;
  return (
    <li>
      <Link
        href={href}
        className="group grid grid-cols-[1.5rem_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1.5 px-4 py-3.5 transition-colors hover:bg-surface-2/70 focus-visible:bg-surface-2 focus-visible:outline-none sm:px-5 md:grid-cols-[1.5rem_minmax(0,1.3fr)_minmax(0,1fr)_7rem_1rem]"
      >
        <span className="self-start pt-0.5 text-sm text-subtle tabular-nums md:self-center">
          {rank}
        </span>
        <span className="min-w-0">
          <span className="block truncate text-sm font-medium">{capitalize(product.name)}</span>
          <span className="block truncate text-xs text-muted" title={product.description}>
            {shortProductName(product.description)} · HS {product.hs6}
          </span>
        </span>
        <ChevronRight
          aria-hidden
          className="h-4 w-4 text-subtle transition-transform group-hover:translate-x-0.5 md:order-last"
        />
        <span className="col-start-2 col-end-4 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 md:col-auto">
          <span className="text-xs text-subtle">Best market</span>
          <span className="truncate text-sm font-medium">{best.market.name}</span>
          <VerdictBadge verdict={best.verdict} />
        </span>
        <span className="col-start-2 col-end-4 text-xs text-muted tabular-nums md:col-auto md:text-right md:text-sm">
          {money(best.market_imports_usd)} · {signedPercent(best.import_growth_3y)}/yr
          <span className="block text-xs text-subtle">{markets} markets ranked</span>
        </span>
      </Link>
    </li>
  );
}

/** One niche: its products for this exporter, strongest opportunity first, each with its best market. */
export function NicheView({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const override = useSearchParams().get("exporter");
  const exporter = useExporter();
  const niche = useNiche(exporter.code, slug);
  const back = withExporter("/app/browse", override);
  const [filter, setFilter] = useState<Tone>("all");
  const [shown, setShown] = useState(PAGE);

  const backLink = (label: string) => (
    <Link
      href={back}
      className="inline-flex items-center gap-1.5 rounded-lg text-sm text-muted hover:text-fg focus-visible:outline-2 focus-visible:outline-brand"
    >
      <ArrowLeft className="h-4 w-4" /> {label}
    </Link>
  );

  if (exporter.pending || (exporter.code && niche.isPending)) {
    return (
      <Page aria-busy>
        <div className="flex flex-col gap-3">
          <Skeleton className="h-5 w-24" />
          <Skeleton className="h-9 w-64" />
          <Skeleton className="h-5 w-full max-w-lg" />
        </div>
        <Skeleton className="h-32 rounded-2xl" />
        <Skeleton className="h-96 rounded-2xl" />
      </Page>
    );
  }
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
  if (niche.isError || !niche.data) {
    const missing = niche.error instanceof ApiError && niche.error.status === 404;
    return (
      <Page>
        {backLink("Explore")}
        <EmptyState
          icon={missing ? <PackageX /> : <RotateCcw />}
          title={missing ? "Niche not found" : "Couldn’t load this niche"}
          action={
            missing ? (
              <ButtonLink href={back}>See all niches</ButtonLink>
            ) : (
              <Button variant="secondary" onClick={() => void niche.refetch()}>
                Try again
              </Button>
            )
          }
        >
          {missing ? "It may have been renamed." : "Check your connection, then try again."}
        </EmptyState>
      </Page>
    );
  }

  const { name, sector, exporter: exp, products } = niche.data;
  const top = products[0];
  const counts = Object.fromEntries(
    FILTERS.map((f) => [
      f.value,
      f.value === "all"
        ? products.length
        : products.filter((p) => VERDICT_TONE[p.best.verdict.action] === f.value).length,
    ]),
  ) as Record<Tone, number>;
  const ranked = products.map((item, i) => ({ item, rank: i + 1 }));
  const visible = ranked.filter(
    ({ item }) => filter === "all" || VERDICT_TONE[item.best.verdict.action] === filter,
  );
  const marketHref = (hs6: string) => withExporter(`/app/markets/${hs6}`, override);

  return (
    <Page>
      <PageHeader
        eyebrow={backLink(`Explore · ${sector}`)}
        title={
          <span className="flex items-center gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-brand-soft text-brand">
              <NicheIcon
                slug={slug}
                sector={sector}
                aria-hidden
                className="h-6 w-6"
                strokeWidth={1.75}
              />
            </span>
            {name}
          </span>
        }
        description={`${products.length} product${products.length === 1 ? "" : "s"} with ranked markets for exporters in ${exp.name}, strongest opportunity first.`}
      />

      {products.length === 0 ? (
        <EmptyState
          icon={<PackageX />}
          title="No ranked products in this niche"
          action={<ButtonLink href={back}>See other niches</ButtonLink>}
        >
          None of its products have enough trade from {exp.name} to rank markets yet.
        </EmptyState>
      ) : (
        <>
          {top && (
            <Card
              className="rise-in flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:p-6"
              style={delay(40)}
            >
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-accent-soft text-accent-strong">
                <Trophy aria-hidden className="h-5 w-5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm text-muted">Strongest opportunity in {name.toLowerCase()}</p>
                <p className="mt-0.5 text-lg font-semibold tracking-tight">
                  {capitalize(top.product.name)} to {top.best.market.name}
                </p>
                <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted">
                  <VerdictBadge verdict={top.best.verdict} />
                  <span className="tabular-nums">
                    {money(top.best.market_imports_usd)} imports ·{" "}
                    {signedPercent(top.best.import_growth_3y)}/yr
                  </span>
                </p>
                <p className="mt-2 text-sm text-muted">
                  <span className="font-medium text-fg">Next: </span>
                  {top.best.verdict.next_step}
                </p>
              </div>
              <ButtonLink
                href={withExporter(
                  `/app/markets/${top.product.hs6}/${top.best.market.code}`,
                  override,
                )}
                variant="secondary"
                className="shrink-0"
              >
                Open market <ArrowRight />
              </ButtonLink>
            </Card>
          )}

          <Card className="rise-in overflow-hidden" style={delay(80)}>
            <div className="flex flex-col gap-3 border-b border-line px-4 pt-4 pb-3 sm:px-5">
              <h2 className="text-base font-semibold tracking-tight">All products</h2>
              {products.length > 6 && (
                <Segmented
                  label="Filter by verdict for the best market"
                  value={filter}
                  onChange={(v) => {
                    setFilter(v);
                    setShown(PAGE);
                  }}
                  items={FILTERS.filter((f) => counts[f.value] > 0).map((f) => ({
                    value: f.value,
                    label: (
                      <>
                        {f.label}{" "}
                        <span className="text-subtle tabular-nums">{counts[f.value]}</span>
                      </>
                    ),
                  }))}
                />
              )}
            </div>
            <ul className="divide-y divide-line">
              {visible.slice(0, shown).map(({ item, rank }) => (
                <Row
                  key={item.product.hs6}
                  item={item}
                  rank={rank}
                  href={marketHref(item.product.hs6)}
                />
              ))}
            </ul>
            {visible.length > shown && (
              <div className="border-t border-line p-3 text-center">
                <Button variant="ghost" onClick={() => setShown((n) => n + PAGE * 2)}>
                  Show more ({visible.length - shown} left)
                </Button>
              </div>
            )}
          </Card>
          <p className="text-xs text-subtle">
            Rankings use CEPII BACI customs data. Each product opens its full list of ranked
            markets.
          </p>
        </>
      )}
    </Page>
  );
}
