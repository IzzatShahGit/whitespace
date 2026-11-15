"use client";

import { useId, useState } from "react";

import type { Country } from "@/lib/api/queries";

const MAX_SHOWN = 8;

/** Type to filter countries, click to add; chosen ones show as removable chips. */
export function CountryMultiSelect({
  countries,
  selected,
  onChange,
  exclude,
}: {
  countries: Country[];
  selected: string[];
  onChange: (codes: string[]) => void;
  exclude?: string;
}) {
  const inputId = useId();
  const [text, setText] = useState("");
  const byCode = new Map(countries.map((c) => [c.code, c]));
  const needle = text.trim().toLowerCase();
  const matches = needle
    ? countries
        .filter(
          (c) =>
            c.code !== exclude &&
            !selected.includes(c.code) &&
            c.name.toLowerCase().includes(needle),
        )
        .slice(0, MAX_SHOWN)
    : [];

  return (
    <div className="flex flex-col gap-3">
      <label htmlFor={inputId} className="sr-only">
        Add a country
      </label>
      <input
        id={inputId}
        type="search"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Type a country, e.g. Germany"
        className="h-11 w-full rounded-xl border border-ink-line bg-ink px-4 text-cream outline-none placeholder:text-sage-dim/70 focus:border-ember/70 focus:ring-2 focus:ring-ember/20"
      />
      {matches.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {matches.map((c) => (
            <button
              key={c.code}
              type="button"
              onClick={() => {
                onChange([...selected, c.code]);
                setText("");
              }}
              className="rounded-full border border-ink-line px-3 py-1 text-sm text-sage transition-colors hover:border-sage-dim hover:text-cream"
            >
              + {c.name}
            </button>
          ))}
        </div>
      )}
      {selected.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label="Markets you already sell to">
          {selected.map((code) => (
            <li
              key={code}
              className="flex items-center gap-1.5 rounded-full bg-tile-3/30 py-1 pr-1.5 pl-3 text-sm"
            >
              {byCode.get(code)?.name ?? code}
              <button
                type="button"
                aria-label={`Remove ${byCode.get(code)?.name ?? code}`}
                onClick={() => onChange(selected.filter((s) => s !== code))}
                className="rounded-full px-1.5 text-sage hover:text-cream"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
