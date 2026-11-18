"use client";

import {
  AlarmClock,
  ArrowRight,
  FileText,
  Gavel,
  Globe2,
  Layers,
  Rocket,
  Sparkles,
  TrendingUp,
  Trophy,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type CSSProperties, type FormEvent, useEffect, useState } from "react";

import { type MapValue, WorldMap } from "@/components/charts/world-map";
import { HowWeDecide, VerdictBadge } from "@/components/markets/verdict";
import { Badge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button";
import { Card, CardHeader, Page, PageHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/empty";
import { Stat } from "@/components/ui/stat";
import { BuyView } from "@/components/views/buy-view";
import { GettingStarted } from "@/components/views/getting-started";
import { GrowRange } from "@/components/views/grow-range";
import { DataNote, Problem } from "@/components/views/states";
import {
  type Dashboard as DashboardData,
  type MarketItem,
  useChatSuggestions,
  useDashboard,
  useMarkets,
  useMe,
  useProfile,
} from "@/lib/api/queries";
import { usePipelineSummary } from "@/lib/api/pipeline";
import { useMyTenders } from "@/lib/api/tenders";
import { capitalize, money, signedPercent } from "@/lib/format";
import { useLocale, useT } from "@/lib/i18n";
import type { MessageKey } from "@/lib/i18n/en";

const delay = (ms: number) => ({ "--delay": `${ms}ms` }) as CSSProperties;
const MAP_MARKETS = 20;
const TOP_LIST = 5;

function greeting(now = new Date()): MessageKey {
  const hour = now.getHours();
  return hour < 12 ? "dashboard.morning" : hour < 18 ? "dashboard.afternoon" : "dashboard.evening";
}

/** Shade 1–5 from the opportunity score (0–1). */
function level(score: number): MapValue["level"] {
  return Math.min(5, Math.max(1, Math.ceil(score * 5))) as MapValue["level"];
}

function OpportunityMap({ data }: { data: DashboardData }) {
  const t = useT();
  const products = data.products;
  const [selected, setSelected] = useState(products[0]?.product.hs6);
  const exporter = data.profile.exporter;
  const markets = useMarkets(exporter.code, selected ?? "");
  const items: MarketItem[] = (markets.data?.pages[0]?.items ?? []).slice(0, MAP_MARKETS);
  const current = products.find((p) => p.product.hs6 === selected) ?? products[0];
  if (!current) return null;

  const values: MapValue[] = items.map((m) => ({
    code: m.market.code,
    name: m.market.name,
    level: level(m.score),
    detail: `#${m.rank} · ${m.verdict.headline} · ${money(m.market_imports_usd)} imports`,
    href: `/app/markets/${current.product.hs6}/${m.market.code}`,
  }));

  return (
    <Card className="rise-in flex flex-col gap-5 p-5 sm:p-6 lg:col-span-2" style={delay(120)}>
      <CardHeader
        icon={<Globe2 />}
        title={t("dashboard.sellBest", { product: current.product.name })}
        description={t("dashboard.sellBestDesc", { count: MAP_MARKETS, country: exporter.name })}
        action={
          <ButtonLink href={`/app/markets/${current.product.hs6}`} variant="secondary" size="sm">
            {t("common.all")} {current.total_markets} <ArrowRight />
          </ButtonLink>
        }
      />
      {products.length > 1 && (
        <div role="radiogroup" aria-label="Product" className="flex flex-wrap gap-2">
          {products.map((p) => (
            <button
              key={p.product.hs6}
              type="button"
              role="radio"
              aria-checked={p.product.hs6 === current.product.hs6}
              onClick={() => setSelected(p.product.hs6)}
              className={`rounded-full border px-3 py-1 text-sm transition-all ${
                p.product.hs6 === current.product.hs6
                  ? "border-brand bg-brand-soft font-medium text-brand"
                  : "border-line text-muted hover:border-line-strong hover:text-fg"
              }`}
            >
              {capitalize(p.product.name)}
            </button>
          ))}
        </div>
      )}
      {markets.isPending ? (
        <Skeleton className="aspect-[96/47] w-full" />
      ) : (
        <WorldMap
          values={values}
          home={exporter.code}
          label={`Map of the best markets for ${current.product.name}`}
        />
      )}
      <ol className="grid gap-1 sm:grid-cols-2">
        {items.slice(0, TOP_LIST + 1).map((m) => (
          <li key={m.market.code}>
            <Link
              href={`/app/markets/${current.product.hs6}/${m.market.code}`}
              className="flex items-center gap-3 rounded-xl px-3 py-2.5 transition-colors hover:bg-surface-2"
            >
              <span className="w-5 text-sm text-subtle tabular-nums">{m.rank}</span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">{m.market.name}</span>
                <span className="text-xs text-muted tabular-nums">
                  {money(m.market_imports_usd)} · {signedPercent(m.import_growth_3y)}/yr
                </span>
              </span>
              <VerdictBadge verdict={m.verdict} />
            </Link>
          </li>
        ))}
      </ol>
    </Card>
  );
}

/** The user's own outreach: follow-ups due today, else where the pipeline stands. */
function FollowUps() {
  const t = useT();
  const summary = usePipelineSummary();
  const s = summary.data;
  if (!s || s.total === 0) return null;
  const active = ["to_contact", "emailed", "replied", "samples", "negotiating"]
    .map((k) => s.by_stage[k] ?? 0)
    .reduce((a, b) => a + b, 0);
  return (
    <Card className="rise-in flex flex-col gap-3 p-5" style={delay(140)}>
      <CardHeader
        icon={<AlarmClock />}
        title={
          s.due.length
            ? t("dashboard.toFollowUp", { count: s.due.length })
            : t("dashboard.yourPipeline")
        }
        description={t("dashboard.pipelineCounts", { active, won: s.by_stage["won"] ?? 0 })}
        action={
          <ButtonLink href="/app/pipeline" variant="secondary" size="sm">
            {t("common.open")} <ArrowRight />
          </ButtonLink>
        }
      />
      {s.due.length > 0 && (
        <ul className="flex flex-col gap-1">
          {s.due.slice(0, 4).map((c) => (
            <li key={c.id}>
              <Link
                href={`/app/pipeline?contact=${c.id}`}
                className="flex items-center justify-between gap-3 rounded-xl px-3 py-2 text-sm transition-colors hover:bg-surface-2"
              >
                <span className="min-w-0 truncate font-medium">{c.name}</span>
                <span className="shrink-0 text-xs text-muted">{c.market_name}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/** Public buyers in Europe asking for the user's products: shown only when there are some. */
function OpenTenders() {
  const t = useT();
  const tenders = useMyTenders();
  const list = tenders.data?.tenders ?? [];
  if (!list.length) return null;
  return (
    <Card className="rise-in flex flex-col gap-3 p-5" style={delay(150)}>
      <CardHeader
        icon={<Gavel />}
        title={t("dashboard.openTenders", { count: list.length })}
        description={t("dashboard.openTendersDesc")}
        action={
          <ButtonLink href="/app/tenders" variant="secondary" size="sm">
            {t("common.all")} <ArrowRight />
          </ButtonLink>
        }
      />
      <ul className="flex flex-col gap-1">
        {list.slice(0, 3).map((tender) => (
          <li key={tender.number}>
            <a
              href={tender.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-between gap-3 rounded-xl px-3 py-2 text-sm transition-colors hover:bg-surface-2"
            >
              <span className="min-w-0 truncate">{tender.buyer}</span>
              <span className="shrink-0 text-xs text-muted">
                {tender.country_names[0]}
                {tender.days_left !== null ? ` · ${tender.days_left}d` : ""}
              </span>
            </a>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function BestMoves({ data }: { data: DashboardData }) {
  const t = useT();
  if (data.best_moves.length === 0) return null;
  return (
    <Card className="rise-in flex flex-col gap-4 p-5" style={delay(160)}>
      <CardHeader
        icon={<Rocket />}
        title={t("dashboard.bestMoves")}
        description={t("dashboard.bestMovesDesc")}
      />
      <ul className="flex flex-col gap-2">
        {data.best_moves.map(({ product, market }) => (
          <li
            key={`${product.hs6}-${market.market.code}`}
            className="relative flex flex-col gap-2 rounded-xl border border-line p-3.5 transition-all focus-within:border-accent/40 hover:-translate-y-0.5 hover:border-accent/40 hover:shadow-card"
          >
            <div className="flex items-center justify-between gap-2">
              {/* The whole card opens the market; the deal sheet link sits above it. */}
              <Link
                href={`/app/markets/${product.hs6}/${market.market.code}`}
                className="font-medium outline-none after:absolute after:inset-0 after:rounded-xl"
              >
                {market.market.name}
              </Link>
              <VerdictBadge verdict={market.verdict} />
            </div>
            <p className="text-xs text-muted">
              {capitalize(product.name)} · {money(market.market_imports_usd)} ·{" "}
              {signedPercent(market.import_growth_3y)}/yr
            </p>
            <p className="text-xs leading-5 text-muted">
              <span className="font-medium text-fg">{t("dashboard.next")} </span>
              {market.verdict.next_step}
            </p>
            <Link
              href={`/app/markets/${product.hs6}/${market.market.code}/deal`}
              className="relative z-10 inline-flex items-center gap-1.5 self-start rounded-md text-xs font-medium text-brand hover:underline"
            >
              <FileText className="h-3.5 w-3.5" aria-hidden /> {t("dashboard.dealSheetLink")}
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function AskCard() {
  const t = useT();
  const router = useRouter();
  const suggestions = useChatSuggestions();
  const [text, setText] = useState("");

  function submit(e: FormEvent) {
    e.preventDefault();
    const q = text.trim();
    router.push(q ? `/app/ask?q=${encodeURIComponent(q)}` : "/app/ask");
  }

  return (
    <Card className="rise-in relative flex flex-col gap-4 overflow-hidden p-5" style={delay(200)}>
      <div
        aria-hidden
        className="pointer-events-none absolute -top-16 -right-16 h-40 w-40 rounded-full bg-accent/15 blur-2xl"
      />
      <CardHeader
        icon={<Sparkles />}
        title={t("dashboard.askWhitespace")}
        description={t("dashboard.askDesc")}
      />
      <form onSubmit={submit} className="flex gap-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={t("dashboard.askPlaceholder")}
          aria-label="Your question"
          className="h-10 min-w-0 flex-1 rounded-xl border border-line bg-canvas px-3 text-sm outline-none focus:border-brand/60 focus:ring-4 focus:ring-brand/10"
        />
        <button
          type="submit"
          aria-label="Ask"
          className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent text-on-accent transition-transform hover:-translate-y-px"
        >
          <ArrowRight className="h-4 w-4" />
        </button>
      </form>
      <div className="flex flex-col gap-1.5">
        {suggestions.data?.prompts.slice(0, 3).map((p) => (
          <Link
            key={p}
            href={`/app/ask?q=${encodeURIComponent(p)}`}
            className="truncate rounded-lg px-2 py-1.5 text-xs text-muted transition-colors hover:bg-surface-2 hover:text-fg"
          >
            {p}
          </Link>
        ))}
      </div>
    </Card>
  );
}

function SellHome() {
  const t = useT();
  const { locale } = useLocale();
  const me = useMe();
  const dashboard = useDashboard(true);

  if (dashboard.isPending) {
    return (
      <Page>
        <Skeleton className="h-16 w-80" />
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
        <Skeleton className="h-[28rem]" />
      </Page>
    );
  }
  if (dashboard.isError) {
    return <Problem title={t("dashboard.loadError")}>Please refresh the page.</Problem>;
  }

  const data = dashboard.data;
  const { profile, products, best_moves: moves } = data;
  const firstName = me.data?.full_name.split(" ")[0];
  const top = moves[0];
  const allTop = products.flatMap((p) => p.top);
  const fastest = allTop.reduce<MarketItem | undefined>(
    (best, m) => (!best || m.import_growth_3y > best.import_growth_3y ? m : best),
    undefined,
  );
  const ranked = products.reduce((sum, p) => sum + p.total_markets, 0);

  return (
    <Page>
      <PageHeader
        eyebrow={new Date().toLocaleDateString(locale, {
          weekday: "long",
          day: "numeric",
          month: "long",
        })}
        title={`${t(greeting())}${firstName ? `, ${firstName}` : ""}`}
        description={t("dashboard.exportingFrom", {
          country: profile.exporter.name,
          products: products.map((p) => p.product.name).join(", "),
        })}
        actions={
          <>
            {profile.goal === "both" && (
              <ButtonLink href="/app/buy" variant="secondary">
                {t("dashboard.findSuppliers")}
              </ButtonLink>
            )}
            <ButtonLink href="/app/ask" variant="accent">
              <Sparkles /> {t("dashboard.askWhitespace")}
            </ButtonLink>
          </>
        }
      />

      <div className="rise-in grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4" style={delay(60)}>
        <Stat
          icon={<Trophy />}
          label={t("dashboard.bestNext")}
          value={top ? top.market.market.name : "—"}
          note={top ? capitalize(top.product.name) : t("dashboard.noMoveYet")}
        />
        <Stat
          icon={<TrendingUp />}
          label={t("dashboard.fastest")}
          value={fastest ? signedPercent(fastest.import_growth_3y) : "—"}
          changeTone="positive"
          note={fastest ? t("dashboard.fastestNote", { market: fastest.market.name }) : undefined}
          explain="How fast the market's imports grew each year over the last three years of customs data."
        />
        <Stat
          icon={<Globe2 />}
          label={t("dashboard.ranked")}
          value={ranked.toLocaleString("en")}
          note={t("dashboard.rankedNote", { count: products.length })}
        />
        <Stat
          icon={<Layers />}
          label={t("dashboard.yourProducts")}
          value={products.length}
          note={
            <Link href="/app/settings/business" className="text-brand hover:underline">
              {t("dashboard.editList")}
            </Link>
          }
        />
      </div>

      <GettingStarted firstProduct={products[0]?.product.hs6} />

      <div className="grid gap-4 lg:grid-cols-3">
        <OpportunityMap data={data} />
        <div className="flex flex-col gap-4">
          <FollowUps />
          <OpenTenders />
          <AskCard />
          <BestMoves data={data} />
        </div>
      </div>

      {products.some((p) => p.top.length === 0) && (
        <p className="text-sm text-muted">
          <Badge tone="neutral">Note</Badge> You already sell to every ranked market for some of
          your products.
        </p>
      )}

      <GrowRange profile={profile} />

      <HowWeDecide />
      {data.data && <DataNote start={data.data.start_year} end={data.data.end_year} />}
    </Page>
  );
}

/** Home: the seller's overview, or the buyer's when buying is all they do. */
export function Dashboard() {
  const router = useRouter();
  const profile = useProfile();
  const needsOnboarding = profile.isSuccess && profile.data === null;

  useEffect(() => {
    if (needsOnboarding) router.replace("/onboarding");
  }, [needsOnboarding, router]);

  if (needsOnboarding) return null;
  if (profile.isPending)
    return (
      <Page>
        <Skeleton className="h-96" />
      </Page>
    );
  if (profile.isError)
    return <Problem title="Couldn’t load your overview">Please refresh.</Problem>;
  return profile.data?.goal === "buy" ? <BuyView /> : <SellHome />;
}
