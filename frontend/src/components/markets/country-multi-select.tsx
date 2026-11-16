"use client";

import { Plus, Search, X } from "lucide-react";
import { type KeyboardEvent, useId, useState } from "react";

import type { Country } from "@/lib/api/queries";

const MAX_SHOWN = 8;
// Where exporters from our countries sell most: one tap instead of typing.
const POPULAR = ["USA", "GBR", "DEU", "ARE", "SAU", "CHN", "NLD", "FRA"];

/** Type to find a country (arrow keys + Enter, or tap); chosen ones show as removable chips. */
export function CountryMultiSelect({
  countries,
  selected,
  onChange,
  exclude,
  label = "Add a country",
  id,
}: {
  countries: Country[];
  selected: string[];
  onChange: (codes: string[]) => void;
  exclude?: string;
  label?: string;
  id?: string;
}) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const listId = useId();
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const byCode = new Map(countries.map((c) => [c.code, c]));
  const available = (c: Country) => c.code !== exclude && !selected.includes(c.code);
  const needle = text.trim().toLowerCase();
  const matches = needle
    ? countries
        .filter((c) => available(c) && c.name.toLowerCase().includes(needle))
        .sort(
          (a, b) =>
            Number(!a.name.toLowerCase().startsWith(needle)) -
            Number(!b.name.toLowerCase().startsWith(needle)),
        )
        .slice(0, MAX_SHOWN)
    : [];
  const popular = POPULAR.map((code) => byCode.get(code)).filter(
    (c): c is Country => c !== undefined && available(c),
  );
  const showList = open && needle.length > 0;

  function add(code: string) {
    onChange([...selected, code]);
    setText("");
    setActive(0);
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((i) => Math.min(i + 1, matches.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && showList && matches[active]) {
      e.preventDefault();
      add(matches[active].code);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <label htmlFor={inputId} className="sr-only">
        {label}
      </label>
      <div className="relative z-30">
        <Search
          aria-hidden
          className="pointer-events-none absolute top-1/2 left-4 h-[18px] w-[18px] -translate-y-1/2 text-subtle"
        />
        <input
          id={inputId}
          type="search"
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={showList && matches[active] ? `${listId}-${active}` : undefined}
          autoComplete="off"
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setOpen(true);
            setActive(0);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={onKeyDown}
          placeholder="Type a country, e.g. Germany"
          className="h-12 w-full rounded-xl border border-line bg-surface pr-4 pl-11 text-base text-fg shadow-card transition-colors outline-none placeholder:text-subtle focus:border-brand/60 focus:ring-4 focus:ring-brand/10"
        />
        {showList && (
          <ul
            id={listId}
            role="listbox"
            aria-label="Matching countries"
            className="pop-in absolute z-30 mt-2 max-h-72 w-full overflow-auto rounded-2xl border border-line bg-surface p-1.5 shadow-pop"
          >
            {matches.length === 0 && (
              <li role="presentation" className="px-3 py-3 text-sm text-muted">
                No country matches “{text.trim()}”.
              </li>
            )}
            {matches.map((c, i) => (
              <li
                key={c.code}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                onMouseDown={(e) => {
                  e.preventDefault();
                  add(c.code);
                }}
                onMouseEnter={() => setActive(i)}
                className={`flex cursor-pointer items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors ${
                  i === active ? "bg-surface-2 text-fg" : "text-fg"
                }`}
              >
                {c.name}
                <Plus aria-hidden className="h-4 w-4 text-subtle" />
              </li>
            ))}
          </ul>
        )}
      </div>

      {!needle && popular.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-subtle">Popular:</span>
          {popular.slice(0, 6).map((c) => (
            <button
              key={c.code}
              type="button"
              onClick={() => add(c.code)}
              className="inline-flex min-h-8 items-center gap-1 rounded-full border border-line bg-surface px-3 text-sm text-muted transition-colors hover:border-line-strong hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
            >
              <Plus aria-hidden className="h-3.5 w-3.5" />
              {c.name}
            </button>
          ))}
        </div>
      )}

      {selected.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label="Chosen countries">
          {selected.map((code) => {
            const name = byCode.get(code)?.name ?? code;
            return (
              <li
                key={code}
                className="pop-in flex items-center gap-1 rounded-full bg-brand-soft py-1 pr-1 pl-3 text-sm font-medium text-brand"
              >
                {name}
                <button
                  type="button"
                  aria-label={`Remove ${name}`}
                  onClick={() => onChange(selected.filter((s) => s !== code))}
                  className="flex h-6 w-6 items-center justify-center rounded-full transition-colors hover:bg-brand/15 focus-visible:outline-2 focus-visible:outline-brand"
                >
                  <X aria-hidden className="h-3.5 w-3.5" />
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
