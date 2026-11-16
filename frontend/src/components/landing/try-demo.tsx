"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  ArrowRight,
  ChevronDown,
  CircleAlert,
  Search,
  SearchX,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { type CSSProperties, type FormEvent, useId, useState, useSyncExternalStore } from "react";

import { VerdictBadge } from "@/components/markets/verdict";
import { Button, ButtonLink } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/empty";
import { inputClass } from "@/components/ui/field";
import { type Preview, usePreview } from "@/lib/api/public";
import { ApiError } from "@/lib/api/queries";
import { money, signedPercent } from "@/lib/format";

/** The ten home countries, each with products people there actually export. */
const COUNTRIES = [
  { code: "PAK", name: "Pakistan", region: "PK", examples: ["rice", "towels", "footballs"] },
  { code: "BGD", name: "Bangladesh", region: "BD", examples: ["t-shirts", "jeans", "jute"] },
  { code: "VNM", name: "Vietnam", region: "VN", examples: ["cashews", "coffee", "shoes"] },
  { code: "IND", name: "India", region: "IN", examples: ["rice", "spices", "cotton yarn"] },
  { code: "TUR", name: "Türkiye", region: "TR", examples: ["carpets", "hazelnuts", "towels"] },
  { code: "EGY", name: "Egypt", region: "EG", examples: ["oranges", "cotton", "onions"] },
  { code: "MAR", name: "Morocco", region: "MA", examples: ["tomatoes", "sardines", "olives"] },
  { code: "KEN", name: "Kenya", region: "KE", examples: ["tea", "flowers", "avocados"] },
  { code: "LKA", name: "Sri Lanka", region: "LK", examples: ["tea", "cinnamon", "gloves"] },
  { code: "ETH", name: "Ethiopia", region: "ET", examples: ["coffee", "sesame", "flowers"] },
] as const;

type Code = (typeof COUNTRIES)[number]["code"];
type Search = { exporter: Code; q: string };

const LANGUAGE_REGION: Record<string, string> = {
  ur: "PK",
  bn: "BD",
  vi: "VN",
  hi: "IN",
  tr: "TR",
  si: "LK",
  am: "ET",
  sw: "KE",
};

/** The visitor's likely home country from the browser's languages ("" on the server). */
function detectCountry(): Code | "" {
  for (const tag of navigator.languages ?? [navigator.language]) {
    const [language, region] = tag.split("-");
    const guess = region?.toUpperCase() || LANGUAGE_REGION[language.toLowerCase()];
    const match = COUNTRIES.find((c) => c.region === guess);
    if (match) return match.code;
  }
  return "PAK";
}
const noSubscribe = () => () => {};

const country = (code: Code) => COUNTRIES.find((c) => c.code === code)!;

function problem(error: unknown, q: string): { title: string; body: string } {
  if (error instanceof ApiError && error.status === 404)
    return {
      title: `We couldn’t find “${q}”`,
      body: "Try a simpler, everyday word, like “towels”, “rice” or “t-shirts”.",
    };
  if (error instanceof ApiError && error.status === 429)
    return { title: "That’s a lot of searches", body: "Please wait a minute, then try again." };
  return { title: "Couldn’t load the markets", body: "Check your connection and try again." };
}

function Results({ data }: { data: Preview }) {
  const product = data.product.name;
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted">
        Top 3 of <span className="font-medium text-fg tabular-nums">{data.total}</span> markets for{" "}
        <span className="font-medium text-fg">{product}</span> from {data.exporter.name}
      </p>
      <ol className="flex flex-col gap-2">
        {data.markets.map((m, i) => {
          const Trend = m.growth < 0 ? TrendingDown : TrendingUp;
          return (
            <li
              key={m.market.code}
              className="rise-in flex items-center gap-3 rounded-xl border border-line bg-surface p-3 sm:gap-4 sm:px-4"
              style={{ "--delay": `${i * 60}ms` } as CSSProperties}
            >
              <span
                aria-hidden
                className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-sm font-semibold tabular-nums ${
                  i === 0 ? "bg-accent-soft text-accent-strong" : "bg-surface-2 text-muted"
                }`}
              >
                {i + 1}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">
                  <span className="sr-only">Number {i + 1}: </span>
                  {m.market.name}
                </p>
                <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-muted tabular-nums">
                  <span>Buys {money(m.imports_usd)} a year</span>
                  <span
                    className={`inline-flex items-center gap-0.5 font-medium ${
                      m.growth < 0 ? "text-negative" : "text-positive"
                    }`}
                  >
                    <Trend aria-hidden className="h-3.5 w-3.5" />
                    {signedPercent(m.growth)}/yr
                  </span>
                </p>
              </div>
              <VerdictBadge verdict={m} />
            </li>
          );
        })}
      </ol>
      <div className="mt-1 flex flex-col gap-3 rounded-xl bg-brand-soft/70 p-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-fg">
          <span className="font-medium">See all {data.total} markets</span>
          <span className="text-muted">, with the reasons, rivals and prices.</span>
        </p>
        <ButtonLink href="/signup" className="shrink-0">
          Start free <ArrowRight />
        </ButtonLink>
      </div>
      <p className="text-xs text-subtle">
        Live from customs data{data.data_year ? `, ${data.data_year}` : ""} (CEPII BACI). Growth is
        a year, over the last three years.
      </p>
    </div>
  );
}

function ResultsSkeleton() {
  return (
    <div className="flex flex-col gap-3" aria-hidden>
      <Skeleton className="h-5 w-64 max-w-full" />
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="h-[62px]" />
      ))}
      <Skeleton className="h-[72px]" />
    </div>
  );
}

function Demo() {
  const id = useId();
  const detected = useSyncExternalStore(noSubscribe, detectCountry, () => "" as const);
  const [chosen, setChosen] = useState<Code | null>(null);
  const [text, setText] = useState<string | null>(null);
  const [search, setSearch] = useState<Search | null>(null);

  const exporter: Code = chosen ?? (detected || "PAK");
  const examples = country(exporter).examples;
  const value = text ?? examples[0];
  // Until the visitor searches, show the first example for their country.
  const active: Search | null = search ?? (detected ? { exporter, q: examples[0] } : null);
  const preview = usePreview(active?.exporter ?? "PAK", active?.q ?? "");

  function run(next: Search) {
    if (next.q.trim().length < 2) return;
    setSearch({ exporter: next.exporter, q: next.q.trim() });
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    run({ exporter, q: value });
  }

  function pickCountry(code: Code) {
    setChosen(code);
    // Typed products stay; otherwise the new country's first example fills in.
    run({ exporter: code, q: text ?? country(code).examples[0] });
  }

  function pickExample(q: string) {
    setText(q);
    run({ exporter, q });
  }

  const status = !active || preview.isPending ? "loading" : preview.isError ? "error" : "ready";

  return (
    <div className="flex flex-col gap-5">
      <form onSubmit={onSubmit} className="flex flex-col gap-3" role="search">
        <div className="grid gap-3 sm:grid-cols-[1fr_11rem]">
          <div className="flex flex-col gap-1.5">
            <label htmlFor={`${id}-q`} className="text-sm font-medium">
              I sell
            </label>
            <div className="relative">
              <Search
                aria-hidden
                className="pointer-events-none absolute top-1/2 left-3.5 h-4 w-4 -translate-y-1/2 text-subtle"
              />
              <input
                id={`${id}-q`}
                value={value}
                onChange={(e) => setText(e.target.value)}
                maxLength={60}
                autoComplete="off"
                enterKeyHint="search"
                placeholder="towels, rice, t-shirts…"
                className={`${inputClass} pl-10 text-base`}
              />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor={`${id}-from`} className="text-sm font-medium">
              From
            </label>
            <div className="relative">
              <select
                id={`${id}-from`}
                value={exporter}
                onChange={(e) => pickCountry(e.target.value as Code)}
                className={`${inputClass} appearance-none pr-10 text-base`}
              >
                {COUNTRIES.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.name}
                  </option>
                ))}
              </select>
              <ChevronDown
                aria-hidden
                className="pointer-events-none absolute top-1/2 right-3.5 h-4 w-4 -translate-y-1/2 text-subtle"
              />
            </div>
          </div>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-1.5 text-sm text-muted">
            <span>Try</span>
            {examples.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => pickExample(q)}
                className="min-h-8 rounded-full border border-line bg-surface px-3 text-sm text-fg transition-colors hover:border-line-strong hover:bg-surface-2 focus-visible:outline-2 focus-visible:outline-brand"
              >
                {q}
              </button>
            ))}
          </div>
          <Button type="submit" variant="secondary" className="h-11 shrink-0">
            Show my markets
          </Button>
        </div>
      </form>

      <div aria-live="polite" aria-busy={status === "loading"} className="min-h-[19rem]">
        {status === "loading" && <ResultsSkeleton />}
        {status === "error" && active && (
          <div className="flex items-start gap-3 rounded-xl border border-line bg-surface-2/60 p-4">
            {preview.error instanceof ApiError && preview.error.status === 404 ? (
              <SearchX aria-hidden className="mt-0.5 h-5 w-5 shrink-0 text-subtle" />
            ) : (
              <CircleAlert aria-hidden className="mt-0.5 h-5 w-5 shrink-0 text-caution" />
            )}
            <div>
              <p className="font-medium">{problem(preview.error, active.q).title}</p>
              <p className="mt-1 text-sm text-muted">{problem(preview.error, active.q).body}</p>
            </div>
          </div>
        )}
        {status === "ready" && preview.data && <Results data={preview.data} />}
      </div>
    </div>
  );
}

/** Try-first: real rankings for the visitor's own product, before any sign-up. */
export function TryDemo() {
  const [client] = useState(
    () => new QueryClient({ defaultOptions: { queries: { refetchOnWindowFocus: false } } }),
  );
  return (
    <QueryClientProvider client={client}>
      <Demo />
    </QueryClientProvider>
  );
}
