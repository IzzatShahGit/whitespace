"use client";

import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  Calculator,
  ExternalLink,
  Flame,
  Sparkles,
  Star,
  TrendingUp,
  Trophy,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { replaceSearchParams } from "@/components/markets/url-state";
import { Badge, Callout } from "@/components/ui/badge";
import { buttonClass } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/empty";
import { Segmented } from "@/components/ui/segmented";
import {
  type AmazonCategory,
  type BestsellerItem,
  type CategoryTrend,
  type Ideas,
  type RisingProduct,
  useIdeas,
} from "@/lib/api/ideas";
import { money, monthLabel, signedPercent } from "@/lib/format";
import { useT } from "@/lib/i18n";

const DEFAULT_CATEGORY = "home";

type Params = Record<string, string | null | undefined>;

type Links = {
  /** The FBA calculator, prefilled. An empty value is kept (it clears the example's). */
  profit: (params: Params) => string;
  /** A page inside the app; signed out, it goes through sign-up first. */
  app: (path: string) => string;
};

function links(signedOut: boolean): Links {
  return {
    profit(params) {
      const query = new URLSearchParams();
      for (const [key, value] of Object.entries(params)) {
        if (value !== null && value !== undefined) query.set(key, value);
      }
      return `${signedOut ? "/fba-calculator" : "/app/fba"}?${query.toString()}`;
    },
    app: (path) => (signedOut ? `/signup?next=${encodeURIComponent(path)}` : path),
  };
}

const num = (value: number | null | undefined, digits = 2) =>
  value === null || value === undefined ? null : String(Number(value.toFixed(digits)));

/** A search phrase from an Amazon title: no brand, no sizes and colours after the first
 * separator, at most six words ("Owala FreeSip Stainless Steel Water Bottle, 24 oz" ->
 * "FreeSip Stainless Steel Water Bottle"). */
function searchPhrase(name: string, brand: string | null): string {
  let text = name.split(/[,|(–—]| - /)[0];
  const at = brand ? text.toLowerCase().indexOf(brand.toLowerCase()) : -1;
  if (brand && at >= 0) text = text.slice(0, at) + text.slice(at + brand.length);
  return text.split(/\s+/).filter(Boolean).slice(0, 6).join(" ");
}

/** Everything the calculator can take from an Amazon product. */
function amazonParams(item: BestsellerItem): Params {
  const size = item.size;
  return {
    hs6: item.hs6 ?? "", // no sure code: the calculator asks for the product
    pn: item.product_name ?? "",
    q: item.hs6 ? null : searchPhrase(item.name, item.brand),
    cat: item.fee_category,
    price: num(item.price_usd),
    u: size ? "imperial" : null,
    l: num(size?.length_in),
    w: num(size?.width_in),
    h: num(size?.height_in),
    wt: num(size?.weight_lb, 3),
    from: item.start?.origin.code,
    cost: num(item.start?.unit_cost_usd),
    src: "amazon",
    an: item.name.slice(0, 110),
  };
}

function date(iso: string): string {
  return new Date(iso).toLocaleDateString("en", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** What sells now (Amazon, weekly) beside what the US imports more of (Census, monthly),
 * for one Amazon category at a time; every product leads to its numbers. */
export function IdeasView({ signedOut = false }: { signedOut?: boolean }) {
  const t = useT();
  const ideas = useIdeas();
  const search = useSearchParams();
  const [category, setCategory] = useState(() => search.get("cat") ?? DEFAULT_CATEGORY);

  if (ideas.isLoading) return <IdeasSkeleton />;
  if (ideas.isError || !ideas.data) {
    return <Callout tone="negative">{ideas.error?.message ?? "Something went wrong."}</Callout>;
  }
  const data = ideas.data;
  const current = data.categories.find((c) => c.key === category) ?? data.categories[0];
  const go = links(signedOut);

  function choose(key: string) {
    setCategory(key);
    replaceSearchParams({ cat: key === DEFAULT_CATEGORY ? null : key });
  }

  return (
    <div className="flex flex-col gap-6">
      <Segmented
        label={t("ideas.category")}
        items={data.categories.map((c) => ({ value: c.key, label: c.label }))}
        value={current.key}
        onChange={choose}
      />
      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
        <AmazonList data={data} category={current} go={go} />
        {data.imports && (
          <HotCategories
            trends={data.imports.categories}
            categories={data.categories}
            selected={current.key}
            onSelect={choose}
          />
        )}
      </div>
      {data.imports && (
        <RisingList
          items={data.imports.rising.filter((r) => r.category === current.key)}
          category={current}
          go={go}
        />
      )}
      <Sources data={data} />
    </div>
  );
}

// --- what sells now ----------------------------------------------------------------

function AmazonList({ data, category, go }: { data: Ideas; category: AmazonCategory; go: Links }) {
  const t = useT();
  const amazon = data.amazon;
  const list = amazon?.lists.find((l) => l.category.key === category.key);
  let description: string | undefined;
  if (amazon) {
    description = t("ideas.amazon.captured", { date: date(amazon.captured_at) });
    if (amazon.previous_at) {
      description += ` · ${t("ideas.amazon.compared", { date: date(amazon.previous_at) })}`;
    }
  }
  return (
    <Card className="rise-in p-4 sm:p-6">
      <CardHeader
        icon={<Trophy />}
        title={`${t("ideas.amazon.title")}: ${category.label}`}
        description={description}
      />
      <a
        href={category.bestsellers_url}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-2 inline-flex min-h-11 items-center gap-1 text-sm text-brand hover:underline sm:ms-12"
      >
        {t("ideas.amazon.openLive")} <ExternalLink className="h-3.5 w-3.5" aria-hidden />
      </a>
      {!amazon ? (
        <p className="mt-4 text-sm text-muted">{t("ideas.amazon.empty")}</p>
      ) : !list ? (
        <p className="mt-4 text-sm text-muted">{t("ideas.amazon.none")}</p>
      ) : (
        <ol className="mt-4 divide-y divide-line">
          {list.items.map((item) => (
            <BestsellerRow key={item.rank} item={item} go={go} />
          ))}
        </ol>
      )}
    </Card>
  );
}

function Movement({ item }: { item: BestsellerItem }) {
  const t = useT();
  if (item.is_new) {
    return (
      <Badge tone="accent" icon={<Sparkles />}>
        {t("ideas.amazon.newEntry")}
      </Badge>
    );
  }
  if (!item.moved) return null;
  return item.moved > 0 ? (
    <Badge tone="positive" icon={<ArrowUp />}>
      {t("ideas.amazon.up", { count: item.moved })}
    </Badge>
  ) : (
    <Badge tone="negative" icon={<ArrowDown />}>
      {t("ideas.amazon.down", { count: -item.moved })}
    </Badge>
  );
}

function BestsellerRow({ item, go }: { item: BestsellerItem; go: Links }) {
  const t = useT();
  const profit = go.profit(amazonParams(item));
  const start = item.start;
  return (
    <li className="grid grid-cols-[2rem_minmax(0,1fr)] gap-x-3 gap-y-3 py-4 sm:grid-cols-[2rem_minmax(0,1fr)_auto] sm:items-center">
      <span className="pt-0.5 text-sm font-semibold text-muted tabular-nums">#{item.rank}</span>
      <div className="min-w-0">
        <Link href={profit} className="line-clamp-2 text-sm font-medium hover:text-brand">
          {item.name}
        </Link>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
          {item.price_usd !== null && (
            <span className="font-semibold text-fg tabular-nums">
              ${item.price_usd.toFixed(2)}
              {item.list_price_usd !== null && (
                <span className="ms-1 font-normal text-subtle line-through">
                  {t("ideas.amazon.listPrice", { price: `$${item.list_price_usd.toFixed(2)}` })}
                </span>
              )}
            </span>
          )}
          {item.stars !== null && (
            <span className="inline-flex items-center gap-1 tabular-nums">
              <Star className="h-3.5 w-3.5" aria-hidden /> {item.stars.toFixed(1)}
              {item.reviews !== null &&
                ` · ${t("ideas.amazon.reviews", { count: item.reviews.toLocaleString("en") })}`}
            </span>
          )}
          {item.bought && <span className="text-positive">{item.bought}</span>}
          <Movement item={item} />
        </div>
        <p className="mt-1 text-xs text-subtle">
          {item.hs6 ? (
            <>
              {t("ideas.amazon.code")}: {item.product_name} ({item.hs6})
              {start &&
                ` · ${
                  start.unit_cost_usd !== null
                    ? t("ideas.amazon.startCost", {
                        country: start.origin.name,
                        cost: `$${start.unit_cost_usd.toFixed(2)}`,
                      })
                    : t("ideas.amazon.startCountry", { country: start.origin.name })
                }`}
            </>
          ) : (
            t("ideas.amazon.noCode")
          )}
        </p>
      </div>
      <div className="col-start-2 flex items-center gap-2 sm:col-start-3">
        <Link href={profit} className={buttonClass("tinted", "flex-1 sm:flex-none")}>
          <Calculator aria-hidden /> {t("ideas.actions.profit")} <ArrowRight aria-hidden />
        </Link>
        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={t("ideas.amazon.view")}
          title={t("ideas.amazon.view")}
          className={buttonClass("ghost", "w-10 px-0")}
        >
          <ExternalLink aria-hidden />
        </a>
      </div>
    </li>
  );
}

// --- what's growing ----------------------------------------------------------------

function HotCategories({
  trends,
  categories,
  selected,
  onSelect,
}: {
  trends: CategoryTrend[];
  categories: AmazonCategory[];
  selected: string;
  onSelect: (key: string) => void;
}) {
  const t = useT();
  const measured = new Set(trends.map((tr) => tr.category.key));
  const unmeasured = categories.filter((c) => !measured.has(c.key));
  return (
    <Card className="rise-in p-4 sm:p-6" style={{ "--delay": "80ms" } as React.CSSProperties}>
      <CardHeader
        icon={<Flame />}
        title={t("ideas.hot.title")}
        description={t("ideas.hot.description")}
      />
      <ul className="mt-4 flex flex-col gap-1">
        {trends.map((tr) => (
          <li key={tr.category.key}>
            <button
              type="button"
              onClick={() => onSelect(tr.category.key)}
              aria-pressed={tr.category.key === selected}
              className={`grid min-h-11 w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-xl px-3 py-2 text-start text-sm transition-colors hover:bg-surface-2 ${
                tr.category.key === selected ? "bg-surface-2 font-medium" : ""
              }`}
            >
              <span className="min-w-0">
                <span className="block truncate">{tr.category.label}</span>
                <span className="block text-xs font-normal text-subtle tabular-nums">
                  {money(tr.imports_usd)}
                  {tr.recent_growth !== null &&
                    ` · ${t("ideas.hot.quarter")} ${signedPercent(tr.recent_growth)}`}
                </span>
              </span>
              {tr.growth !== null && (
                <Badge tone={tr.growth >= 0 ? "positive" : "negative"}>
                  {signedPercent(tr.growth)}
                </Badge>
              )}
            </button>
          </li>
        ))}
        {unmeasured.map((c) => (
          <li
            key={c.key}
            className="flex min-h-11 items-center justify-between gap-3 px-3 text-sm text-subtle"
          >
            <span className="truncate">{c.label}</span>
            <span className="text-xs">{t("ideas.hot.noData")}</span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-muted">{t("ideas.hot.note")}</p>
    </Card>
  );
}

function Bars({ values }: { values: number[] }) {
  const peak = Math.max(1, ...values);
  return (
    <div className="flex h-10 w-full max-w-40 items-end gap-[2px]" aria-hidden>
      {values.map((v, i) => (
        <div
          key={i}
          // The latest 12 months in full colour, the year before faded: the comparison.
          className={`flex-1 rounded-t-sm ${i >= values.length - 12 ? "bg-brand/70" : "bg-brand/25"}`}
          style={{ height: `${Math.max(4, (v / peak) * 100)}%` }}
        />
      ))}
    </div>
  );
}

function RisingList({
  items,
  category,
  go,
}: {
  items: RisingProduct[];
  category: AmazonCategory;
  go: Links;
}) {
  const t = useT();
  return (
    <Card className="rise-in p-4 sm:p-6" style={{ "--delay": "140ms" } as React.CSSProperties}>
      <CardHeader
        icon={<TrendingUp />}
        title={t("ideas.rising.title", { category: category.label })}
        description={t("ideas.rising.description")}
      />
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-muted">{t("ideas.rising.none")}</p>
      ) : (
        <ul className="mt-4 divide-y divide-line">
          {items.map((r) => (
            <li
              key={r.hs6}
              className="grid grid-cols-1 gap-3 py-4 md:grid-cols-[minmax(0,1fr)_10rem_auto] md:items-center md:gap-6"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium">
                  {r.name} <span className="font-normal text-subtle">· {r.hs6}</span>
                </p>
                <div className="mt-1.5 flex flex-wrap items-center gap-2">
                  <Badge tone="positive">
                    {t("ideas.rising.growth", { change: signedPercent(r.growth) })}
                  </Badge>
                  {r.recent_growth !== null && (
                    <span className="text-xs text-muted">
                      {t("ideas.rising.recent", { change: signedPercent(r.recent_growth) })}
                    </span>
                  )}
                  <span className="text-xs text-muted tabular-nums">
                    {t("ideas.rising.perYear", { value: money(r.imports_usd) })}
                  </span>
                </div>
                {r.china_extra_pct !== null && (
                  <p className="mt-1.5 text-xs text-subtle">
                    {r.china_extra_pct > 0
                      ? t("ideas.rising.china", { rate: r.china_extra_pct })
                      : t("ideas.rising.chinaNone")}
                  </p>
                )}
              </div>
              <Bars values={r.monthly_usd} />
              {r.in_catalog ? (
                <div className="flex flex-wrap gap-2">
                  <Link
                    href={go.profit({
                      hs6: r.hs6,
                      pn: r.name,
                      cat: r.fee_category,
                      from: r.start?.origin.code,
                      src: "imports",
                    })}
                    className={buttonClass("tinted")}
                  >
                    <Calculator aria-hidden /> {t("ideas.actions.profit")}
                  </Link>
                  <Link
                    href={go.app(`/app/buy/${r.hs6}`)}
                    className={buttonClass("ghost", "", "sm")}
                  >
                    {t("ideas.actions.suppliers")}
                  </Link>
                  <Link
                    href={go.app(`/app/markets/${r.hs6}`)}
                    className={buttonClass("ghost", "", "sm")}
                  >
                    {t("ideas.actions.markets")}
                  </Link>
                </div>
              ) : (
                <p className="text-xs text-subtle">{t("ideas.rising.notCovered")}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

// --- sources -----------------------------------------------------------------------

function Sources({ data }: { data: Ideas }) {
  const t = useT();
  return (
    <details className="rounded-2xl border border-line bg-surface px-4 py-3 text-sm sm:px-6">
      <summary className="cursor-pointer font-medium select-none">
        {t("ideas.sources.title")}
      </summary>
      <ul className="mt-3 flex list-disc flex-col gap-2 ps-5 text-muted">
        <li>{t("ideas.sources.amazon")}</li>
        {data.imports && (
          <li>
            {t("ideas.sources.imports", {
              source: data.imports.source,
              from: monthLabel(data.imports.first_month),
              to: monthLabel(data.imports.last_month),
            })}
          </li>
        )}
        <li>{t("ideas.sources.codes")}</li>
        <li>{t("ideas.sources.affiliation")}</li>
      </ul>
    </details>
  );
}

function IdeasSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <Skeleton className="h-10 w-full" />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
        <Skeleton className="h-[32rem]" />
        <Skeleton className="h-[32rem]" />
      </div>
    </div>
  );
}
