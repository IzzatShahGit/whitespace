"use client";

import { ArrowUpDown, ChevronDown, Search, X } from "lucide-react";

import { VERDICT_ICON, VERDICT_TONE } from "@/components/markets/verdict";
import type { MarketItem, Verdict } from "@/lib/api/queries";

export type Action = Verdict["action"];
export type VerdictFilter = "all" | Action;
export type SortKey = "rank" | "size" | "growth" | "share";

/** Verdicts in the order people act on them: go, grow, test, defend, care, hard. */
export const ACTIONS: Action[] = ["go", "grow", "test", "defend", "care", "hard"];

export const SORTS: Record<
  SortKey,
  { label: string; compare: (a: MarketItem, b: MarketItem) => number }
> = {
  rank: { label: "Best match", compare: (a, b) => a.rank - b.rank },
  size: {
    label: "Biggest market",
    compare: (a, b) => b.market_imports_usd - a.market_imports_usd || a.rank - b.rank,
  },
  growth: {
    label: "Fastest growing",
    compare: (a, b) => b.import_growth_3y - a.import_growth_3y || a.rank - b.rank,
  },
  share: {
    label: "Your biggest share",
    compare: (a, b) => b.exporter_share - a.exporter_share || a.rank - b.rank,
  },
};

export const parseSort = (value: string | null): SortKey =>
  value && value in SORTS ? (value as SortKey) : "rank";

export const parseVerdict = (value: string | null): VerdictFilter =>
  ACTIONS.includes(value as Action) ? (value as Action) : "all";

/** "Türkiye" matches "turkiye": lower case, accents removed. */
const fold = (text: string) => text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

export function selectMarkets(
  items: MarketItem[],
  { verdict, query, sort }: { verdict: VerdictFilter; query: string; sort: SortKey },
): MarketItem[] {
  const q = fold(query);
  return items
    .filter((m) => verdict === "all" || m.verdict.action === verdict)
    .filter((m) => !q || fold(m.market.name).includes(q) || m.market.code.toLowerCase() === q)
    .sort(SORTS[sort].compare);
}

const TONE_TEXT = { positive: "text-positive", caution: "text-caution", negative: "text-negative" };

const chip =
  "inline-flex h-10 shrink-0 items-center gap-1.5 rounded-full border px-3.5 text-sm transition-colors duration-150 " +
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand sm:h-9";

/** One chip per verdict (with how many markets carry it), plus "All". */
export function VerdictChips({
  value,
  onChange,
  total,
  counts,
}: {
  value: VerdictFilter;
  onChange: (value: VerdictFilter) => void;
  total: number;
  counts: { action: Action; label: string; count: number }[] | null; // null while loading
}) {
  const state = (selected: boolean) =>
    selected
      ? "border-brand bg-brand-soft font-medium text-brand"
      : "border-line bg-surface text-muted hover:border-line-strong hover:text-fg";
  return (
    <div
      role="group"
      aria-label="Filter by verdict"
      className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0 sm:pb-0"
    >
      <button
        type="button"
        aria-pressed={value === "all"}
        onClick={() => onChange("all")}
        className={`${chip} ${state(value === "all")}`}
      >
        All <span className="text-subtle tabular-nums">{total}</span>
      </button>
      {counts
        ? counts.map(({ action, label, count }) => {
            const Icon = VERDICT_ICON[action];
            const tone = VERDICT_TONE[action] as keyof typeof TONE_TEXT;
            return (
              <button
                key={action}
                type="button"
                aria-pressed={value === action}
                onClick={() => onChange(value === action ? "all" : action)}
                className={`${chip} ${state(value === action)}`}
              >
                <Icon className={`h-4 w-4 ${TONE_TEXT[tone]}`} aria-hidden />
                {label}
                <span className="text-subtle tabular-nums">{count}</span>
              </button>
            );
          })
        : [0, 1, 2, 3].map((i) => (
            <span key={i} aria-hidden className="skeleton h-10 w-32 shrink-0 rounded-full sm:h-9" />
          ))}
    </div>
  );
}

const control =
  "h-11 rounded-xl border border-line bg-surface text-fg shadow-card outline-none transition-colors " +
  "focus:border-brand/60 focus:ring-4 focus:ring-brand/10";

export function MarketSearch({
  value,
  onChange,
}: {
  value: string;
  onChange: (q: string) => void;
}) {
  return (
    <div className="relative min-w-0 flex-1 sm:max-w-xs">
      <Search
        aria-hidden
        className="pointer-events-none absolute top-1/2 left-3.5 h-4 w-4 -translate-y-1/2 text-subtle"
      />
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Find a market"
        aria-label="Find a market by name"
        autoComplete="off"
        enterKeyHint="search"
        className={`${control} w-full pr-10 pl-10 placeholder:text-subtle [&::-webkit-search-cancel-button]:hidden`}
      />
      {value && (
        <button
          type="button"
          aria-label="Clear search"
          onClick={() => onChange("")}
          className="absolute top-1/2 right-1.5 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-lg text-subtle transition-colors hover:bg-surface-2 hover:text-fg focus-visible:outline-2 focus-visible:outline-brand"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}

export function SortSelect({
  value,
  onChange,
}: {
  value: SortKey;
  onChange: (s: SortKey) => void;
}) {
  return (
    <label className="relative flex shrink-0 items-center">
      <span className="sr-only">Sort markets</span>
      <ArrowUpDown
        aria-hidden
        className="pointer-events-none absolute left-3.5 h-4 w-4 text-subtle"
      />
      <select
        value={value}
        onChange={(e) => onChange(parseSort(e.target.value))}
        className={`${control} w-40 appearance-none truncate pr-9 pl-10 text-base sm:w-auto sm:text-sm`}
      >
        {(Object.keys(SORTS) as SortKey[]).map((key) => (
          <option key={key} value={key}>
            {SORTS[key].label}
          </option>
        ))}
      </select>
      <ChevronDown
        aria-hidden
        className="pointer-events-none absolute right-3 h-4 w-4 text-subtle"
      />
    </label>
  );
}
