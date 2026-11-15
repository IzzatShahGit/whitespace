"use client";

import { useId } from "react";

import { useFxRates } from "@/lib/api/queries";
import { currencyName } from "@/lib/currency";
import { localMoney, parseAmount, parseKg, weight } from "@/lib/money";

/** Convert between any currency and US dollars at today's rate (one shared rates query). */
export function useConverter(currency: string) {
  const fx = useFxRates();
  const perUsd = currency === "USD" ? 1 : fx.data?.rates[currency];
  return {
    perUsd,
    rates: fx.data,
    pending: currency !== "USD" && fx.isPending,
    failed: currency !== "USD" && (fx.isError || (fx.isSuccess && perUsd === undefined)),
    toUsd: (local: number) => (perUsd ? local / perUsd : undefined),
    toLocal: (dollars: number) => (perUsd ? dollars * perUsd : undefined),
  };
}

/** Suggested currencies first, then every currency the rates service knows. */
export function CurrencySelect({
  value,
  onChange,
  suggested,
  className = "",
}: {
  value: string;
  onChange: (currency: string) => void;
  suggested: string[];
  className?: string;
}) {
  const fx = useFxRates();
  const all = Object.keys(fx.data?.rates ?? {})
    .filter((code) => !suggested.includes(code))
    .sort((a, b) => currencyName(a).localeCompare(currencyName(b)));
  return (
    <select
      aria-label="Currency"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={`bg-ink-raised px-3 text-sm text-sage outline-none ${className}`}
    >
      <optgroup label="Suggested">
        {suggested.map((code) => (
          <option key={code} value={code} title={currencyName(code)}>
            {code}
          </option>
        ))}
      </optgroup>
      {all.length > 0 && (
        <optgroup label="All currencies">
          {all.map((code) => (
            <option key={code} value={code}>
              {code} · {currencyName(code)}
            </option>
          ))}
        </optgroup>
      )}
    </select>
  );
}

const fieldClass =
  "flex h-11 items-stretch overflow-hidden rounded-xl border border-ink-line bg-ink transition-colors " +
  "focus-within:border-ember/70 focus-within:ring-2 focus-within:ring-ember/20";

function Echo({ text, children }: { text: string; children: string | null }) {
  // Repeats back how we read the input, so "18 lakh" never silently becomes 18.
  return (
    <span aria-live="polite" className="min-h-4 text-xs text-sage-dim">
      {text.trim() && (children ?? "Try a number like 18 lakh, 2.5 crore or 1,250,000")}
    </span>
  );
}

/** An amount in the user's currency or dollars; understands lakh, crore, k, million. */
export function AmountField({
  label,
  text,
  onText,
  currency,
  onCurrency,
  currencies,
  placeholder = "e.g. 18 lakh",
}: {
  label: string;
  text: string;
  onText: (text: string) => void;
  currency: string;
  onCurrency: (currency: string) => void;
  currencies: string[]; // offered first
  placeholder?: string;
}) {
  const id = useId();
  const value = parseAmount(text);
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm text-cream">
        {label}
      </label>
      <div className={fieldClass}>
        <input
          id={id}
          inputMode="decimal"
          autoComplete="off"
          value={text}
          placeholder={placeholder}
          onChange={(e) => onText(e.target.value)}
          className="min-w-0 flex-1 bg-transparent px-4 text-cream outline-none placeholder:text-sage-dim/70"
        />
        <CurrencySelect
          value={currency}
          onChange={onCurrency}
          suggested={currencies}
          className="w-24 border-l border-ink-line"
        />
      </div>
      <Echo text={text}>{value === null ? null : localMoney(value, currency)}</Echo>
    </div>
  );
}

/** A quantity in kg or tonnes ("5 tons", "750 kg"). */
export function WeightField({
  label,
  text,
  onText,
}: {
  label: string;
  text: string;
  onText: (text: string) => void;
}) {
  const id = useId();
  const kg = parseKg(text);
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm text-cream">
        {label} <span className="text-sage-dim">(optional)</span>
      </label>
      <div className={fieldClass}>
        <input
          id={id}
          inputMode="decimal"
          autoComplete="off"
          value={text}
          placeholder="e.g. 5 tons or 800 kg"
          onChange={(e) => onText(e.target.value)}
          className="min-w-0 flex-1 bg-transparent px-4 text-cream outline-none placeholder:text-sage-dim/70"
        />
      </div>
      <span aria-live="polite" className="min-h-4 text-xs text-sage-dim">
        {text.trim() && (kg === null ? "Try 5 tons, 5000 kg or 2.5 t" : weight(kg))}
      </span>
    </div>
  );
}

/** Where the rate comes from (the free service asks for attribution). */
export function RateNote({ currency }: { currency: string }) {
  const { rates, perUsd, failed } = useConverter(currency);
  if (currency === "USD") return null;
  if (failed) {
    return <p className="text-xs text-caution">No exchange rate for {currency} right now.</p>;
  }
  if (!rates || !perUsd) return null;
  return (
    <p className="text-xs text-sage-dim">
      1 USD = {perUsd.toLocaleString("en", { maximumFractionDigits: 2 })} {currency} ·{" "}
      <a
        href="https://www.exchangerate-api.com"
        target="_blank"
        rel="noreferrer"
        className="underline-offset-4 hover:text-sage hover:underline"
      >
        Rates by {rates.source}
      </a>
      , updated {rates.updated.slice(0, 16)}
    </p>
  );
}
