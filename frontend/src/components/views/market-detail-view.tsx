"use client";

import {
  ArrowLeft,
  ClipboardCheck,
  BarChart3,
  Building2,
  CalendarClock,
  Footprints,
  Globe2,
  LayoutGrid,
  MapPinOff,
  Scale,
  Columns3,
  FileText,
  Sparkles,
  Target,
  TrendingDown,
  TrendingUp,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { type CSSProperties, type ReactNode, use, useEffect } from "react";

import { LeadsPanel } from "@/components/leads/leads-panel";
import { RequirementsPanel } from "@/components/requirements/requirements-panel";
import { FreightEstimate } from "@/components/money/freight-estimate";
import { BriefPanel } from "@/components/markets/brief-panel";
import { LoadError } from "@/components/markets/load-error";
import { RecentPanel } from "@/components/markets/recent-panel";
import { SupplierChart } from "@/components/markets/supplier-chart";
import { replaceSearchParams } from "@/components/markets/url-state";
import { HowWeDecide, SellingBadge, SignalGrid, VerdictBadge } from "@/components/markets/verdict";
import { DutyAdvantage } from "@/components/money/landed-cost";
import { PriceCheck } from "@/components/money/price-check";
import { ButtonLink } from "@/components/ui/button";
import { Card, CardHeader, Page, PageHeader } from "@/components/ui/card";
import { EmptyState, Skeleton } from "@/components/ui/empty";
import { Stat } from "@/components/ui/stat";
import { type TabItem, Tabs } from "@/components/ui/tabs";
import { DataNote } from "@/components/views/states";
import { WatchButton } from "@/components/watch/watch-button";
import {
  ApiError,
  type MarketDetail,
  type Signal,
  useMarketDetail,
  useRecentMovement,
} from "@/lib/api/queries";
import { money, percent, points, signedPercent } from "@/lib/format";
import { markStep } from "@/lib/steps";
import { useT } from "@/lib/i18n";
import type { MessageKey } from "@/lib/i18n/en";
import { useExporter, withExporter } from "@/lib/use-exporter";

const delay = (ms: number) => ({ "--delay": `${ms}ms` }) as CSSProperties;

type TabKey = "overview" | "needs" | "buyers" | "competitors" | "prices" | "recent";

const TABS: Record<TabKey, { short: MessageKey; long: MessageKey; icon: ReactNode }> = {
  overview: { short: "market.tabOverview", long: "market.tabOverview", icon: <LayoutGrid /> },
  needs: { short: "market.tabNeedsShort", long: "market.tabNeeds", icon: <ClipboardCheck /> },
  buyers: { short: "market.tabBuyersShort", long: "market.tabBuyers", icon: <Building2 /> },
  competitors: {
    short: "market.tabCompetitorsShort",
    long: "market.tabCompetitors",
    icon: <Users />,
  },
  prices: { short: "market.tabPricesShort", long: "market.tabPrices", icon: <Scale /> },
  recent: { short: "market.tabRecentShort", long: "market.tabRecent", icon: <CalendarClock /> },
};

function BackLink({ href, children }: { href: string; children: ReactNode }) {
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

function DetailSkeleton() {
  return (
    <Page aria-busy className="gap-6">
      <div className="flex flex-col gap-3">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-9 w-56" />
        <Skeleton className="h-5 w-72 max-w-full" />
      </div>
      <Skeleton className="h-44 rounded-2xl" />
      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-28 rounded-2xl" />
        ))}
      </div>
      <Skeleton className="h-11" />
      <Skeleton className="h-72 rounded-2xl" />
    </Page>
  );
}

/** One market in depth: the verdict and next step, four numbers, then the evidence in tabs. */
export function MarketDetailView({ params }: { params: Promise<{ hs6: string; market: string }> }) {
  const t = useT();
  const { hs6, market } = use(params);
  const search = useSearchParams();
  const override = search.get("exporter");
  const exporter = useExporter();
  const code = market.toUpperCase();
  useEffect(() => markStep("market"), []); // getting-started checklist
  const detail = useMarketDetail(exporter.code, hs6, code);
  const recent = useRecentMovement(exporter.code, hs6, code);
  const back = withExporter(`/app/markets/${hs6}`, override);

  if (exporter.pending || (exporter.code && detail.isPending)) return <DetailSkeleton />;
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
  if (!detail.data) {
    const missing = detail.error instanceof ApiError && detail.error.status === 404;
    return (
      <Page>
        {missing ? (
          <EmptyState
            icon={<MapPinOff />}
            title="Not a ranked market for this product"
            action={
              <ButtonLink href={back} variant="secondary">
                See the ranked markets
              </ButtonLink>
            }
          >
            {detail.error?.message}. Markets are ranked when they import enough and you have a real
            chance there.
          </EmptyState>
        ) : (
          <LoadError
            title="Couldn’t load this market"
            onRetry={() => void detail.refetch()}
            retrying={detail.isFetching}
            action={
              <ButtonLink href={back} variant="ghost">
                Back to the ranking
              </ButtonLink>
            }
          >
            Check your connection and try again.
          </LoadError>
        )}
      </Page>
    );
  }

  // The monthly tab appears for markets with a monthly source (EU members and the US).
  const keys: TabKey[] = ["overview", "needs", "buyers", "competitors", "prices"];
  const requested = search.get("tab") as TabKey | null;
  if (recent.data || (requested === "recent" && recent.isPending)) keys.push("recent");
  const tab: TabKey = requested && keys.includes(requested) ? requested : "overview";
  const items: TabItem<TabKey>[] = keys.map((key) => ({
    value: key,
    label: (
      <>
        <span className="hidden sm:inline-flex [&>svg]:h-4 [&>svg]:w-4">{TABS[key].icon}</span>
        <span className="sm:hidden">{t(TABS[key].short)}</span>
        <span className="hidden sm:inline">{t(TABS[key].long)}</span>
      </>
    ),
  }));

  return (
    <Detail
      data={detail.data}
      back={back}
      tab={tab}
      tabs={items}
      onTab={(next) => replaceSearchParams({ tab: next === "overview" ? null : next })}
      ownCountry={!override}
    />
  );
}

function Detail({
  data,
  back,
  tab,
  tabs,
  onTab,
  ownCountry,
}: {
  data: MarketDetail;
  back: string;
  tab: TabKey;
  tabs: TabItem<TabKey>[];
  onTab: (tab: TabKey) => void;
  ownCountry: boolean;
}) {
  const t = useT();
  const { exporter: exp, product, data: years, market: m, suppliers } = data;
  const signal = (kind: Signal["kind"]) => m.signals.find((s) => s.kind === kind);
  const tone = (s?: Signal) => s?.tone ?? "neutral";
  const own = suppliers.find((s) => s.country.code === exp.code);
  const ownChange = own ? own.share_end - own.share_start : undefined;
  const rival = m.top_rival;
  const shareLabel = ownCountry ? "Your share" : `${exp.name}’s share`;
  const ask = `/app/ask?q=${encodeURIComponent(
    `Tell me about ${m.market.name} for my ${product.name}`,
  )}`;
  const since = `since ${years.start_year}`;

  return (
    <Page className="gap-6">
      <PageHeader
        eyebrow={<BackLink href={back}>All markets for {product.name}</BackLink>}
        title={m.market.name}
        description={
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            For {product.name} from {exp.name} · ranked #{m.rank}
            {m.already_selling && <SellingBadge />}
          </span>
        }
        actions={
          <>
            <WatchButton exporter={exp.code} hs6={product.hs6} market={m.market.code} />
            <ButtonLink
              href={`/app/markets/${product.hs6}/${m.market.code}/deal`}
              variant="secondary"
            >
              <FileText /> Deal sheet
            </ButtonLink>
            <ButtonLink
              href={`/app/markets/${product.hs6}/compare?m=${m.market.code}`}
              variant="secondary"
            >
              <Columns3 /> Compare
            </ButtonLink>
            <ButtonLink href={ask} variant="accent">
              <Sparkles /> Ask about this
            </ButtonLink>
          </>
        }
      />

      <Card className="rise-in p-5 sm:p-6" style={delay(60)}>
        <VerdictBadge verdict={m.verdict} large />
        <p
          dir="auto"
          className="mt-3 max-w-3xl text-lg leading-7 text-pretty sm:text-xl sm:leading-8"
        >
          {m.verdict.summary}
        </p>
        <div className="mt-5 flex items-start gap-3 rounded-xl bg-surface-2/70 p-3.5 sm:p-4">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-soft text-brand">
            <Footprints className="h-4 w-4" aria-hidden />
          </span>
          <div>
            <p className="text-xs font-medium text-muted">Your next step</p>
            <p dir="auto" className="mt-0.5 text-[15px] leading-6 text-fg">
              {m.verdict.next_step}
            </p>
          </div>
        </div>
      </Card>

      <div className="rise-in grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4" style={delay(100)}>
        <Stat
          icon={<BarChart3 />}
          label="Market size"
          value={money(m.market_imports_usd)}
          note={`imports in ${years.end_year}`}
          explain={`What ${m.market.name} imported of ${product.name} in ${years.end_year}, from every country, at customs value in US dollars.`}
        />
        <Stat
          icon={m.import_growth_3y < 0 ? <TrendingDown /> : <TrendingUp />}
          label="Growth a year"
          value={signedPercent(m.import_growth_3y)}
          change={signal("demand")?.title}
          changeTone={tone(signal("demand"))}
          note={`${years.start_year}–${years.end_year}`}
          explain={`The average yearly change in ${m.market.name}'s imports from ${years.start_year} to ${years.end_year}.`}
        />
        <Stat
          icon={<Target />}
          label={shareLabel}
          value={percent(m.exporter_share, { floor: true })}
          change={ownChange !== undefined ? points(ownChange) : undefined}
          changeTone={
            ownChange === undefined || Math.round(ownChange * 100) === 0
              ? "neutral"
              : ownChange > 0
                ? "positive"
                : "negative"
          }
          note={ownChange !== undefined ? since : `of imports in ${years.end_year}`}
          explain={`How much of ${m.market.name}'s imports came from ${exp.name} in ${years.end_year}.`}
        />
        <Stat
          icon={<Users />}
          label="Main rival"
          value={
            rival ? (
              <span className={rival.name.length > 12 ? "text-xl" : undefined}>{rival.name}</span>
            ) : (
              "None"
            )
          }
          change={
            rival && m.top_rival_share_change !== null
              ? points(m.top_rival_share_change)
              : undefined
          }
          changeTone={tone(signal("competition"))}
          note={
            rival && m.top_rival_share !== null
              ? `${since} · holds ${percent(m.top_rival_share, { floor: true })}`
              : "no other big supplier"
          }
          explain={`The biggest other supplier, its share of imports in ${years.end_year} and how it moved ${since}. A rival losing share leaves room for you.`}
        />
      </div>

      <div className="rise-in flex flex-col gap-4" style={delay(140)}>
        <Tabs label="Market evidence" items={tabs} value={tab} onChange={onTab} />
        <div
          key={tab}
          role="tabpanel"
          aria-label={t(TABS[tab].long)}
          className="flex flex-col gap-4 transition-[opacity,translate] duration-200 motion-reduce:transition-none starting:translate-y-1 starting:opacity-0"
        >
          {tab === "overview" && (
            <>
              <Card className="p-5 sm:p-6">
                <CardHeader
                  icon={<LayoutGrid />}
                  title={`Why we say “${m.verdict.headline}”`}
                  description={`Four signals from customs data, ${years.start_year}–${years.end_year}.`}
                />
                <div className="mt-5">
                  <SignalGrid signals={m.signals} />
                </div>
              </Card>
              <BriefPanel
                exporter={exp.code}
                hs6={product.hs6}
                market={m.market.code}
                marketName={m.market.name}
              />
              <HowWeDecide />
            </>
          )}
          {tab === "needs" && (
            <RequirementsPanel
              hs6={product.hs6}
              market={m.market.code}
              marketName={m.market.name}
              exporter={exp.code}
              exporterName={exp.name}
              productName={product.name}
            />
          )}
          {tab === "buyers" && (
            <LeadsPanel
              hs6={product.hs6}
              country={m.market.code}
              countryName={m.market.name}
              productName={product.name}
              side="buyers"
            />
          )}
          {tab === "competitors" &&
            (suppliers.length > 0 ? (
              <SupplierChart
                suppliers={suppliers}
                startYear={years.start_year}
                endYear={years.end_year}
                highlight={exp.code}
                marketName={m.market.name}
                exporterName={exp.name}
              />
            ) : (
              <EmptyState icon={<Users />} title="No supplier breakdown">
                Customs data for {m.market.name} doesn’t list its suppliers for this product.
              </EmptyState>
            ))}
          {tab === "prices" && (
            <>
              <FreightEstimate origin={exp.code} dest={m.market.code} hs6={product.hs6} />
              <DutyAdvantage
                exporter={exp.code}
                hs6={product.hs6}
                market={m.market.code}
                marketName={m.market.name}
              />
              <PriceCheck
                exporter={exp.code}
                exporterName={exp.name}
                hs6={product.hs6}
                market={m.market.code}
                marketName={m.market.name}
                averagePrice={m.market_unit_price_usd_kg ?? null}
                suppliers={suppliers}
              />
            </>
          )}
          {tab === "recent" && (
            <RecentPanel
              exporter={exp.code}
              exporterName={exp.name}
              hs6={product.hs6}
              market={m.market.code}
              annualEndYear={years.end_year}
            />
          )}
        </div>
      </div>

      <DataNote start={years.start_year} end={years.end_year} />
    </Page>
  );
}
