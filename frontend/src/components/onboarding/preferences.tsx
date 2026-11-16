"use client";

/*
 * The business preferences model, shared by onboarding (one question per screen) and
 * Settings → Business (every field on one page). One set of rules for both:
 * - products are checked against ranked markets (selling) or supplier data (buying),
 *   so switching between those modes clears them;
 * - rankings are built per country, so changing the country clears products and markets.
 */

import {
  ArrowLeftRight,
  Briefcase,
  Check,
  Compass,
  Landmark,
  type LucideIcon,
  PackageSearch,
  Store,
  TrendingUp,
  X,
} from "lucide-react";
import { type ReactNode, useState } from "react";

import { CountryMultiSelect } from "@/components/markets/country-multi-select";
import { ProductPicker } from "@/components/markets/product-picker";
import type { Country, Goal, Mode, Product, Profile, ProfileInput, Role } from "@/lib/api/queries";
import { capitalize, shortProductName } from "@/lib/format";

export const MAX_PRODUCTS = 5;

export type Draft = {
  goal: Goal;
  exporter: string | undefined;
  role: Role | undefined;
  products: Product[];
  markets: string[];
};

export const productMode = (goal: Goal): Mode => (goal === "buy" ? "buy" : "sell");
export const sellsAbroad = (goal: Goal) => goal !== "buy";

function fromProfile(profile: Profile | null): Draft {
  return {
    goal: profile?.goal ?? "sell",
    exporter: profile?.exporter.code,
    role: profile?.role,
    products: profile?.products ?? [],
    markets: profile?.current_markets.map((c) => c.code) ?? [],
  };
}

/** True when the draft differs from what's saved. */
export function changed(draft: Draft, profile: Profile | null): boolean {
  const saved = fromProfile(profile);
  const same = (a: string[], b: string[]) => a.join() === b.join();
  return (
    draft.goal !== saved.goal ||
    draft.exporter !== saved.exporter ||
    draft.role !== saved.role ||
    !same(
      draft.products.map((p) => p.hs6),
      saved.products.map((p) => p.hs6),
    ) ||
    (sellsAbroad(draft.goal) && !same(draft.markets, saved.markets))
  );
}

/** Editable preferences with the reset rules built in. */
export function usePreferences(initial: Profile | null) {
  const [draft, setDraft] = useState<Draft>(() => fromProfile(initial));
  // Why something was cleared, so a reset never looks like a bug.
  const [notice, setNotice] = useState<string>();

  function chooseGoal(goal: Goal) {
    if (goal === draft.goal) return;
    const reset = productMode(goal) !== productMode(draft.goal);
    if (reset && draft.products.length > 0) {
      setNotice(
        goal === "buy"
          ? "We cleared your products: for buying, pick products with supplier data."
          : "We cleared your products: for selling, pick products with ranked markets.",
      );
    }
    setDraft((d) => ({ ...d, goal, products: reset ? [] : d.products }));
  }

  function chooseExporter(code: string) {
    if (code === draft.exporter) return;
    if (draft.products.length > 0 || draft.markets.length > 0) {
      setNotice("We cleared your products and markets: rankings are built for each country.");
    }
    setDraft((d) => ({ ...d, exporter: code, products: [], markets: [] }));
  }

  const missing = {
    exporter: !draft.exporter,
    role: !draft.role,
    products: draft.products.length === 0,
  };

  function input(): ProfileInput | null {
    if (!draft.exporter || !draft.role || draft.products.length === 0) return null;
    return {
      exporter: draft.exporter,
      role: draft.role,
      goal: draft.goal,
      products: draft.products.map((p) => p.hs6),
      current_markets: sellsAbroad(draft.goal) ? draft.markets : [],
    };
  }

  return {
    draft,
    notice,
    dismissNotice: () => setNotice(undefined),
    missing,
    input,
    reset: (profile: Profile | null) => {
      setDraft(fromProfile(profile));
      setNotice(undefined);
    },
    chooseGoal,
    chooseExporter,
    chooseRole: (role: Role) => setDraft((d) => ({ ...d, role })),
    addProduct: (p: Product) =>
      setDraft((d) =>
        d.products.length >= MAX_PRODUCTS || d.products.some((x) => x.hs6 === p.hs6)
          ? d
          : { ...d, products: [...d.products, p] },
      ),
    removeProduct: (hs6: string) =>
      setDraft((d) => ({ ...d, products: d.products.filter((p) => p.hs6 !== hs6) })),
    setMarkets: (markets: string[]) => setDraft((d) => ({ ...d, markets })),
  };
}

// ---------- options ----------
type Option<T> = { value: T; label: string; hint: string; icon: LucideIcon };

export const GOALS: Option<Goal>[] = [
  {
    value: "sell",
    label: "Sell abroad",
    hint: "Find the best markets for what I make or stock",
    icon: TrendingUp,
  },
  {
    value: "buy",
    label: "Buy from abroad",
    hint: "Find the best countries to source from",
    icon: PackageSearch,
  },
  { value: "both", label: "Both", hint: "I export, and I import inputs", icon: ArrowLeftRight },
];

export function roleOptions(goal: Goal): Option<Role>[] {
  const own =
    goal === "buy"
      ? { label: "Importer", hint: "I buy from abroad for my business" }
      : goal === "both"
        ? { label: "Exporter & importer", hint: "I trade for my own business" }
        : { label: "Exporter", hint: "I sell my own products abroad" };
  return [
    { value: "exporter", ...own, icon: Store },
    { value: "consultant", label: "Consultant", hint: "I advise businesses", icon: Briefcase },
    {
      value: "agency",
      label: "Trade agency",
      hint: "Chamber or promotion body",
      icon: Landmark,
    },
    { value: "other", label: "Other", hint: "Just exploring", icon: Compass },
  ];
}

// The device's time zone is a good first guess at where the business is.
const ZONES: Record<string, string> = {
  "Asia/Karachi": "PAK",
  "Asia/Dhaka": "BGD",
  "Asia/Kolkata": "IND",
  "Asia/Calcutta": "IND",
  "Asia/Colombo": "LKA",
  "Asia/Ho_Chi_Minh": "VNM",
  "Asia/Saigon": "VNM",
  "Africa/Cairo": "EGY",
  "Africa/Addis_Ababa": "ETH",
  "Africa/Nairobi": "KEN",
  "Africa/Casablanca": "MAR",
  "Europe/Istanbul": "TUR",
};

export function guessCountry(): string | undefined {
  try {
    return ZONES[Intl.DateTimeFormat().resolvedOptions().timeZone];
  } catch {
    return undefined;
  }
}

// ---------- controls ----------
/** A big, tappable radio: a real <input type="radio">, so arrow keys and forms just work. */
export function ChoiceCard({
  name,
  value,
  checked,
  onChange,
  icon,
  title,
  hint,
  badge,
  compact = false,
}: {
  name: string;
  value: string;
  checked: boolean;
  onChange: () => void;
  icon: ReactNode;
  title: string;
  hint?: string;
  badge?: string;
  compact?: boolean;
}) {
  return (
    <label
      className={`relative flex cursor-pointer items-center gap-3 rounded-2xl border bg-surface transition-all duration-150 has-focus-visible:ring-4 has-focus-visible:ring-brand/25 ${
        compact ? "min-h-14 px-3.5 py-3" : "min-h-16 p-4"
      } ${
        checked
          ? "border-brand bg-brand-soft shadow-card"
          : "border-line shadow-card hover:border-line-strong"
      }`}
    >
      <input
        type="radio"
        name={name}
        value={value}
        checked={checked}
        onChange={onChange}
        className="sr-only"
      />
      <span
        aria-hidden
        className={`flex shrink-0 items-center justify-center rounded-xl transition-colors ${
          compact ? "h-9 w-9" : "h-10 w-10"
        } ${checked ? "bg-brand text-on-brand" : "bg-surface-2 text-muted"}`}
      >
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-2 text-sm font-medium text-fg">
          {title}
          {badge && (
            <span className="rounded-full bg-surface-2 px-2 py-0.5 text-xs font-normal text-muted">
              {badge}
            </span>
          )}
        </span>
        {hint && <span className="mt-0.5 block text-xs leading-5 text-muted">{hint}</span>}
      </span>
      <span
        aria-hidden
        className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border transition-colors ${
          checked ? "border-brand bg-brand text-on-brand" : "border-line-strong"
        }`}
      >
        {checked && <Check className="h-3.5 w-3.5" strokeWidth={3} />}
      </span>
    </label>
  );
}

const iconClass = "h-5 w-5";

export function GoalField({
  value,
  onChange,
  compact,
  label,
}: {
  value: Goal;
  onChange: (goal: Goal) => void;
  compact?: boolean;
  label: string;
}) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={`grid gap-3 ${compact ? "sm:grid-cols-3" : ""}`}
    >
      {GOALS.map((g) => (
        <ChoiceCard
          key={g.value}
          name="goal"
          value={g.value}
          checked={value === g.value}
          onChange={() => onChange(g.value)}
          icon={<g.icon className={iconClass} />}
          title={g.label}
          hint={g.hint}
          compact={compact}
        />
      ))}
    </div>
  );
}

export function CountryField({
  exporters,
  value,
  onChange,
  suggested,
  label,
}: {
  exporters: Country[];
  value: string | undefined;
  onChange: (code: string) => void;
  suggested?: string;
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
      {exporters.map((c) => (
        <ChoiceCard
          key={c.code}
          name="country"
          value={c.code}
          checked={value === c.code}
          onChange={() => onChange(c.code)}
          icon={<span className="font-mono text-xs font-semibold tracking-wide">{c.code}</span>}
          title={c.name}
          hint={c.code === suggested ? "Matches your time zone" : undefined}
          compact
        />
      ))}
    </div>
  );
}

export function RoleField({
  goal,
  value,
  onChange,
  label,
}: {
  goal: Goal;
  value: Role | undefined;
  onChange: (role: Role) => void;
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="grid gap-3 sm:grid-cols-2">
      {roleOptions(goal).map((r) => (
        <ChoiceCard
          key={r.value}
          name="role"
          value={r.value}
          checked={value === r.value}
          onChange={() => onChange(r.value)}
          icon={<r.icon className={iconClass} />}
          title={r.label}
          hint={r.hint}
          compact
        />
      ))}
    </div>
  );
}

export function ProductsField({
  goal,
  exporter,
  products,
  onAdd,
  onRemove,
  autoFocus,
}: {
  goal: Goal;
  exporter: string | undefined;
  products: Product[];
  onAdd: (product: Product) => void;
  onRemove: (hs6: string) => void;
  autoFocus?: boolean;
}) {
  const full = products.length >= MAX_PRODUCTS;
  const mode = productMode(goal);
  return (
    <div className="flex flex-col gap-3">
      <ProductPicker
        mode={mode}
        exporter={exporter}
        exclude={products.map((p) => p.hs6)}
        disabled={full}
        autoFocus={autoFocus}
        label={mode === "buy" ? "Search products you buy" : "Search products you sell"}
        placeholder={
          full
            ? `That's the maximum of ${MAX_PRODUCTS}. Remove one to add another.`
            : mode === "buy"
              ? "What do you buy? e.g. cotton yarn"
              : "What do you sell? e.g. cotton towels"
        }
        onSelect={onAdd}
      />
      <div className="flex items-center justify-between text-xs text-muted">
        <span>
          {mode === "buy"
            ? "Products with supplier data, in everyday words or an HS code."
            : "Products with ranked markets for your country, in everyday words or an HS code."}
        </span>
        <span className="shrink-0 tabular-nums" aria-live="polite">
          {products.length} of {MAX_PRODUCTS}
        </span>
      </div>
      {products.length > 0 && (
        <ul className="flex flex-col gap-2" aria-label="Your products">
          {products.map((p) => (
            <li
              key={p.hs6}
              className="pop-in flex items-center gap-3 rounded-2xl border border-line bg-surface py-2.5 pr-2 pl-4 shadow-card"
            >
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium">{capitalize(p.name)}</span>
                <span className="block truncate text-xs text-muted" title={p.description}>
                  {shortProductName(p.description)} · HS {p.hs6}
                </span>
              </span>
              <button
                type="button"
                aria-label={`Remove ${p.name} (HS ${p.hs6})`}
                onClick={() => onRemove(p.hs6)}
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-subtle transition-colors hover:bg-surface-2 hover:text-fg focus-visible:outline-2 focus-visible:outline-brand"
              >
                <X className="h-4 w-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function MarketsField({
  countries,
  exporter,
  selected,
  onChange,
}: {
  countries: Country[];
  exporter: string | undefined;
  selected: string[];
  onChange: (codes: string[]) => void;
}) {
  return (
    <CountryMultiSelect
      countries={countries}
      selected={selected}
      onChange={onChange}
      exclude={exporter}
      label="Add a market you already sell to"
    />
  );
}
