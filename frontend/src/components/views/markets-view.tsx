"use client";

import {
  ArrowLeft,
  ArrowLeftRight,
  ChevronDown,
  CircleCheck,
  Globe2,
  Info,
  List,
  Map as MapIcon,
  PackageSearch,
  SearchX,
  Sparkles,
  TrendingUp,
  Trophy,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { type CSSProperties, use, useEffect, useMemo, useState } from "react";

import { type MapValue, WorldMap } from "@/components/charts/world-map";
import { LoadError } from "@/components/markets/load-error";
import { MarketRow, MarketRowSkeleton, ROW_GRID } from "@/components/markets/market-card";
import {
  type Action,
  ACTIONS,
  MarketSearch,
  parseSort,
  parseVerdict,
  selectMarkets,
  type SortKey,
  SORTS,
  SortSelect,
  VerdictChips,
  type VerdictFilter,
} from "@/components/markets/market-toolbar";
import { replaceSearchParams, useMediaQuery } from "@/components/markets/url-state";
import { HowWeDecide, VERDICT_TONE } from "@/components/markets/verdict";
import { Button, ButtonLink, buttonClass } from "@/components/ui/button";
import { Card, CardHeader, Page, PageHeader } from "@/components/ui/card";
import { EmptyState, Skeleton } from "@/components/ui/empty";
import { MenuItem, Popover } from "@/components/ui/menu";
import { Stat, StatGroup } from "@/components/ui/stat";
import { Tabs } from "@/components/ui/tabs";
import { DataNote } from "@/components/views/states";
import {
  ApiError,
  MARKETS_PAGE_SIZE,
  type MarketItem,
  type MarketsPage,
  useMarkets,
  useProfile,
} from "@/lib/api/queries";
import { capitalize, money, shortProductName, signedPercent } from "@/lib/format";
import { useExporter, withExporter } from "@/lib/use-exporter";

const delay = (ms: number) => ({ "--delay": `${ms}ms` }) as CSSProperties;

/** Shade 1–5 from the opportunity score (0–1), as on Home. */
function level(score: number): MapValue["level"] {
  return Math.min(5, Math.max(1, Math.ceil(score * 5))) as MapValue["level"];
}

function maxBy(items: MarketItem[], value: (m: MarketItem) => number): MarketItem | undefined {
  return items.reduce<MarketItem | undefined>(
    (best, m) => (!best || value(m) > value(best) ? m : best),
    undefined,
  );
}

function BackLink({ href, children }: { href: string; children: string }) {
  return (
    <Link
      href={href}
      className="inline-flex items-center gap-1.5 rounded-lg text-sm text-muted transition-colors hover:text-fg focus-visible:outline-2 focus-visible:outline-brand"
    >
      <ArrowLeft className="h-4 w-4" aria-hidden />
      {children}
    </Link>
  );
}

function MarketsSkeleton() {
  return (
    <Page aria-busy>
      <div className="flex flex-col gap-3">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-9 w-48" />
        <Skeleton className="h-5 w-full max-w-md" />
      </div>
      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-28 rounded-2xl" />
        ))}
      </div>
      <div className="flex flex-col gap-3">
        <Skeleton className="h-11 w-full max-w-md" />
        <Card className="overflow-hidden">
          <ul>
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <MarketRowSkeleton key={i} />
            ))}
          </ul>
        </Card>
      </div>
    </Page>
  );
}

/** Every ranked market for one product: summary, filters, a ranked list and a map. */
export function MarketsView({ params }: { params: Promise<{ hs6: string }> }) {
  const { hs6 } = use(params);
  const override = useSearchParams().get("exporter");
  const exporter = useExporter();
  const markets = useMarkets(exporter.code, hs6);

  // Pages are small (20), so the rest load in the background: filters, sorting and the
  // summary then cover every ranked market, and "Show more" is instant.
  const { hasNextPage, isFetchingNextPage, isFetchNextPageError, fetchNextPage } = markets;
  useEffect(() => {
    if (hasNextPage && !isFetchingNextPage && !isFetchNextPageError) void fetchNextPage();
  }, [hasNextPage, isFetchingNextPage, isFetchNextPageError, fetchNextPage]);

  if (exporter.pending || (exporter.code && markets.isPending)) return <MarketsSkeleton />;
  if (!exporter.code) {
    return (
      <Page>
        <EmptyState
          icon={<Globe2 />}
          title="Pick your country first"
          action={<ButtonLink href="/onboarding">Set up your business</ButtonLink>}
        >
          Markets are ranked for exporters in a specific country.
        </EmptyState>
      </Page>
    );
  }
  if (!markets.data) {
    const missing = markets.error instanceof ApiError && markets.error.status < 500;
    return (
      <Page>
        <LoadError
          title={missing ? "We don’t know this product" : "Couldn’t load the markets"}
          onRetry={missing ? undefined : () => void markets.refetch()}
          retrying={markets.isFetching}
          action={
            <ButtonLink href="/app/markets" variant="ghost">
              Search products
            </ButtonLink>
          }
        >
          {missing
            ? (markets.error?.message ?? "Check the product code and try again.")
            : "Check your connection and try again."}
        </LoadError>
      </Page>
    );
  }

  return (
    <MarketsContent
      pages={markets.data.pages}
      override={override}
      loadingMore={Boolean(hasNextPage)}
      loadFailed={isFetchNextPageError}
      onRetry={() => void fetchNextPage()}
    />
  );
}

function MarketsContent({
  pages,
  override,
  loadingMore,
  loadFailed,
  onRetry,
}: {
  pages: MarketsPage[];
  override: string | null;
  loadingMore: boolean;
  loadFailed: boolean;
  onRetry: () => void;
}) {
  const search = useSearchParams();
  const profile = useProfile();
  const wide = useMediaQuery("(min-width: 80rem)");
  const [verdict, setVerdict] = useState<VerdictFilter>(() => parseVerdict(search.get("verdict")));
  const [sort, setSort] = useState<SortKey>(() => parseSort(search.get("sort")));
  const [query, setQuery] = useState(() => search.get("q") ?? "");
  const [limit, setLimit] = useState(MARKETS_PAGE_SIZE);
  const [view, setView] = useState<"list" | "map">("list");

  const { product, exporter, total, data } = pages[0];
  const all = useMemo(() => pages.flatMap((p) => p.items), [pages]);
  const complete = !loadingMore;
  const matches = useMemo(
    () => selectMarkets(all, { verdict, query, sort }),
    [all, verdict, query, sort],
  );
  const narrowed = verdict !== "all" || query.trim() !== "" || sort !== "rank";
  const waiting = narrowed && !complete; // results would be partial until every page is in
  const shown = matches.slice(0, limit);
  const name = capitalize(product.name);
  const ownCountry = profile.data?.exporter;
  const advisorView = Boolean(override && ownCountry && ownCountry.code !== exporter.code);
  const link = (code: string) => withExporter(`/app/markets/${product.hs6}/${code}`, override);

  const counts = useMemo(() => {
    if (!complete) return null;
    return ACTIONS.flatMap((action) => {
      const withIt = all.filter((m) => m.verdict.action === action);
      return withIt.length
        ? [{ action, label: withIt[0].verdict.headline, count: withIt.length }]
        : [];
    });
  }, [all, complete]);

  function chooseVerdict(next: VerdictFilter) {
    setVerdict(next);
    replaceSearchParams({ verdict: next === "all" ? null : next });
  }
  function chooseSort(next: SortKey) {
    setSort(next);
    replaceSearchParams({ sort: next === "rank" ? null : next });
  }
  function type(next: string) {
    setQuery(next);
    replaceSearchParams({ q: next.trim() || null });
  }
  function clear() {
    setVerdict("all");
    setQuery("");
    replaceSearchParams({ verdict: null, q: null });
  }

  if (total === 0) {
    return (
      <Page>
        <PageHeader
          eyebrow={<BackLink href="/app/markets">Where to sell</BackLink>}
          title={name}
          description={`${shortProductName(product.description)} · HS ${product.hs6}`}
        />
        <EmptyState
          icon={<PackageSearch />}
          title={`No ranked markets for ${product.name} yet`}
          action={
            <ButtonLink href="/app/markets" variant="secondary">
              Try another product
            </ButtonLink>
          }
        >
          A market is ranked when it imports at least $10M a year and exporters in {exporter.name}{" "}
          have a real chance there. None passed for this product.
        </EmptyState>
      </Page>
    );
  }

  const others = (profile.data?.products ?? []).filter((p) => p.hs6 !== product.hs6);
  const values: MapValue[] = matches.map((m) => ({
    code: m.market.code,
    name: m.market.name,
    level: level(m.score),
    detail: `#${m.rank} · ${m.verdict.headline} · ${money(m.market_imports_usd)} imports`,
    href: link(m.market.code),
  }));

  return (
    <Page className="gap-6 sm:gap-8">
      <PageHeader
        eyebrow={<BackLink href="/app/markets">Where to sell</BackLink>}
        title={name}
        description={
          <>
            {total} markets ranked for exporters in{" "}
            <span className="font-medium text-fg">{exporter.name}</span>, best match first.
            <span className="mt-1 block text-sm text-subtle">
              {shortProductName(product.description)} · HS {product.hs6}
            </span>
          </>
        }
        actions={
          <>
            {others.length > 0 && (
              <Popover
                label="Switch product"
                align="end"
                button={() => (
                  <span className={buttonClass("secondary")}>
                    <ArrowLeftRight /> Switch product
                  </span>
                )}
              >
                {(close) =>
                  others.map((p) => (
                    <MenuItem
                      key={p.hs6}
                      href={withExporter(`/app/markets/${p.hs6}`, override)}
                      onClick={close}
                    >
                      {capitalize(p.name)}
                    </MenuItem>
                  ))
                }
              </Popover>
            )}
            <ButtonLink
              href={`/app/ask?q=${encodeURIComponent(`Where should I sell my ${product.name}?`)}`}
              variant="accent"
            >
              <Sparkles /> Ask about {product.name}
            </ButtonLink>
          </>
        }
      />

      {advisorView && (
        <p className="rise-in flex flex-wrap items-center gap-x-2 gap-y-1 rounded-xl bg-brand-soft px-4 py-3 text-sm text-fg">
          <Info className="h-4 w-4 text-brand" aria-hidden />
          Showing markets for exporters in {exporter.name}.
          <Link
            href={`/app/markets/${product.hs6}`}
            className="font-medium text-brand underline-offset-4 hover:underline"
          >
            Back to {ownCountry?.name}
          </Link>
        </p>
      )}

      <Summary items={all} complete={complete} total={total} endYear={data?.end_year} />

      <section className="rise-in flex flex-col gap-4" style={delay(120)} aria-label="Markets">
        <div className="flex flex-col gap-3">
          <div className="flex gap-2">
            <MarketSearch value={query} onChange={type} />
            <SortSelect value={sort} onChange={chooseSort} />
          </div>
          <VerdictChips value={verdict} onChange={chooseVerdict} total={total} counts={counts} />
        </div>

        <div className="flex min-h-10 items-center justify-between gap-3">
          <p className="text-sm text-muted" aria-live="polite">
            {waiting
              ? `Looking through all ${total} markets…`
              : narrowed
                ? `${matches.length} of ${total} markets · ${SORTS[sort].label.toLowerCase()} first`
                : `Showing ${Math.min(limit, matches.length)} of ${total} markets`}
          </p>
          <div className="w-fit xl:hidden">
            <Tabs
              label="Show markets as"
              value={view}
              onChange={setView}
              items={[
                { value: "list", label: "List", icon: <List /> },
                { value: "map", label: "Map", icon: <MapIcon /> },
              ]}
            />
          </div>
        </div>

        <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_26rem]">
          <Card className={`overflow-hidden ${view === "map" ? "hidden xl:block" : ""}`}>
            <div
              className={`${ROW_GRID} hidden border-b border-line px-4 py-2.5 text-xs font-medium text-subtle sm:px-5 md:grid`}
            >
              <span>#</span>
              <span>Market and verdict</span>
              <ColumnSort
                label="Imports"
                active={sort === "size"}
                onClick={() => chooseSort("size")}
              />
              <ColumnSort
                label="Growth / yr"
                active={sort === "growth"}
                onClick={() => chooseSort("growth")}
              />
              <ColumnSort
                label="Your share"
                active={sort === "share"}
                onClick={() => chooseSort("share")}
              />
              <span />
            </div>
            {waiting ? (
              <ul aria-busy>
                {[0, 1, 2, 3].map((i) => (
                  <MarketRowSkeleton key={i} />
                ))}
              </ul>
            ) : matches.length === 0 ? (
              <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
                <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-surface-2 text-subtle">
                  <SearchX className="h-6 w-6" aria-hidden />
                </span>
                <p className="font-medium">
                  {query.trim() ? `No market matches “${query.trim()}”` : "No markets here"}
                </p>
                <p className="max-w-xs text-sm text-muted">
                  Only the {total} markets ranked for this product are listed. Check the spelling or
                  clear the filters.
                </p>
                <Button variant="secondary" onClick={clear}>
                  Clear filters
                </Button>
              </div>
            ) : (
              <ul className="divide-y divide-line/70">
                {shown.map((m) => (
                  <MarketRow key={m.market.code} item={m} href={link(m.market.code)} />
                ))}
                {!narrowed && loadingMore && shown.length < limit && <MarketRowSkeleton />}
              </ul>
            )}
            {loadFailed ? (
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3 sm:px-5">
                <p className="text-sm text-muted">Couldn’t load the rest of the list.</p>
                <Button variant="secondary" size="sm" onClick={onRetry}>
                  Try again
                </Button>
              </div>
            ) : (
              !waiting &&
              matches.length > limit && (
                <div className="border-t border-line p-3">
                  <Button
                    variant="ghost"
                    className="w-full"
                    onClick={() => setLimit((l) => l + MARKETS_PAGE_SIZE)}
                  >
                    Show {Math.min(MARKETS_PAGE_SIZE, matches.length - limit)} more <ChevronDown />
                  </Button>
                </div>
              )
            )}
          </Card>

          <Card
            className={`flex flex-col gap-4 p-5 xl:sticky xl:top-20 ${
              view === "list" ? "hidden xl:flex" : ""
            }`}
          >
            <CardHeader
              icon={<Globe2 />}
              title="On the map"
              description={`${matches.length} market${matches.length === 1 ? "" : "s"}, shaded by opportunity. Tap one to open it.`}
            />
            {wide || view === "map" ? (
              <WorldMap
                values={values}
                home={exporter.code}
                label={`Map of ${matches.length} ranked markets for ${product.name}`}
              />
            ) : (
              <Skeleton className="aspect-[96/47] w-full" />
            )}
          </Card>
        </div>

        <p className="text-xs leading-5 text-subtle">
          <span className="font-medium text-muted">Imports</span>: what each market bought from all
          countries in {data?.end_year}. <span className="font-medium text-muted">Growth</span>:
          average yearly change, {data?.start_year}–{data?.end_year}.{" "}
          <span className="font-medium text-muted">Your share</span>: the part that came from{" "}
          {exporter.name}.
        </p>
      </section>

      <HowWeDecide />
      {data && <DataNote start={data.start_year} end={data.end_year} />}
    </Page>
  );
}

function ColumnSort({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      aria-label={`Sort by ${label.toLowerCase()}`}
      className={`inline-flex items-center justify-end gap-1 justify-self-end rounded-md transition-colors hover:text-fg focus-visible:outline-2 focus-visible:outline-brand ${
        active ? "text-fg" : ""
      }`}
    >
      {label}
      {active && <ChevronDown className="h-3.5 w-3.5" aria-hidden />}
    </button>
  );
}

/** Four headline numbers for the product, once every market is in. */
function Summary({
  items,
  complete,
  total,
  endYear,
}: {
  items: MarketItem[];
  complete: boolean;
  total: number;
  endYear?: number;
}) {
  const placeholder = <span className="skeleton inline-block h-7 w-24 align-middle" />;
  const positive = (m: MarketItem) => VERDICT_TONE[m.verdict.action as Action] === "positive";
  const top =
    items.find((m) => m.verdict.action === "go" && !m.already_selling) ??
    items.find(positive) ??
    items[0];
  const goAhead = items.filter(positive).length;
  const biggest = maxBy(items, (m) => m.market_imports_usd);
  const fastest = maxBy(items, (m) => m.import_growth_3y);

  return (
    <StatGroup className="rise-in" style={delay(60)}>
      <Stat
        icon={<Trophy />}
        label="Top pick"
        value={top?.market.name ?? "—"}
        note={top ? `${top.verdict.headline} · #${top.rank}` : undefined}
        explain="The best-ranked market where the verdict is Go for it, leaving out markets you already sell to."
      />
      <Stat
        icon={<CircleCheck />}
        label="Worth going after"
        value={complete ? goAhead : placeholder}
        note={`of ${total} say go or grow`}
        explain="Markets whose verdict is Go for it or Grow your lead."
      />
      <Stat
        icon={<Globe2 />}
        label="Biggest market"
        value={complete && biggest ? money(biggest.market_imports_usd) : placeholder}
        note={complete && biggest ? `${biggest.market.name}, ${endYear ?? ""}` : undefined}
        explain="The ranked market that imports the most of this product in a year."
      />
      <Stat
        icon={<TrendingUp />}
        label="Fastest growing"
        value={complete && fastest ? signedPercent(fastest.import_growth_3y) : placeholder}
        note={complete && fastest ? `${fastest.market.name}, a year` : undefined}
        explain="The ranked market whose imports grew fastest each year over the last three years of customs data."
      />
    </StatGroup>
  );
}
