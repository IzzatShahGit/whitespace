"use client";

import { PackageSearch, Search, Sparkles } from "lucide-react";
import { type KeyboardEvent, useId, useState } from "react";

import { HsFinder } from "@/components/markets/hs-finder";
import { type Mode, type ProductOption, useProductSearch } from "@/lib/api/queries";
import { capitalize, shortProductName } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { useDebounced } from "@/lib/use-debounced";

/**
 * Search-as-you-type for products, as an accessible combobox
 * (arrow keys, Enter to pick, Escape to close). Selling lists products with ranked
 * markets from `exporter`; buying lists products with supplier data.
 */
export function ProductPicker({
  mode = "sell",
  exporter,
  onSelect,
  exclude = [],
  placeholder = "Describe your product, e.g. cotton towels",
  disabled = false,
  label,
  id,
  autoFocus = false,
  initialText = "",
}: {
  mode?: Mode;
  exporter: string | undefined;
  onSelect: (product: ProductOption) => void;
  exclude?: string[];
  placeholder?: string;
  disabled?: boolean;
  /** Accessible name when there's no visible <label for={id}>. */
  label?: string;
  id?: string;
  autoFocus?: boolean;
  /** Start with this search typed in (e.g. a product name brought from another page). */
  initialText?: string;
}) {
  const t = useT();
  const listId = useId();
  const [text, setText] = useState(initialText);
  const [finding, setFinding] = useState(false);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const query = useDebounced(text);
  const search = useProductSearch(mode, exporter, query);

  const options = (search.data ?? []).filter((p) => !exclude.includes(p.hs6));
  const showList = open && query.trim().length >= 2;
  const waiting = search.isFetching && !search.data;
  const off = disabled || (mode === "sell" && !exporter);

  function pick(product: ProductOption) {
    onSelect(product);
    setText("");
    setOpen(false);
    setActive(0);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setActive((i) => Math.min(i + 1, options.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (event.key === "Enter" && showList && options[active]) {
      event.preventDefault();
      pick(options[active]);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      {/* Own stacking layer above later page sections: animated sections (transform) each
        create a stacking context, which would otherwise paint over the open list. */}
      <div className="relative z-40">
        <Search
          aria-hidden
          className="pointer-events-none absolute top-1/2 left-4 h-[18px] w-[18px] -translate-y-1/2 text-subtle"
        />
        <input
          id={id}
          type="search"
          role="combobox"
          aria-label={label ?? (id ? undefined : placeholder)}
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={showList && options[active] ? `${listId}-${active}` : undefined}
          autoComplete="off"
          autoFocus={autoFocus}
          value={text}
          disabled={off}
          placeholder={placeholder}
          onChange={(e) => {
            setText(e.target.value);
            setOpen(true);
            setActive(0);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={onKeyDown}
          className="h-12 w-full rounded-xl border border-line bg-surface pr-4 pl-11 text-base text-fg shadow-card transition-colors outline-none placeholder:text-subtle focus:border-brand/60 focus:ring-4 focus:ring-brand/10 disabled:cursor-not-allowed disabled:opacity-60"
        />
        {showList && (
          <ul
            id={listId}
            role="listbox"
            aria-label="Matching products"
            className="pop-in absolute z-30 mt-2 max-h-96 w-full overflow-auto rounded-2xl border border-line bg-surface p-1.5 shadow-pop"
          >
            {waiting && (
              <li role="presentation" className="px-3 py-3 text-sm text-muted">
                Searching…
              </li>
            )}
            {!waiting && options.length === 0 && (
              <li
                role="presentation"
                className="flex items-start gap-3 px-3 py-3 text-sm text-muted"
              >
                <PackageSearch aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-subtle" />
                <span>
                  No products match “{query.trim()}”. Try simpler words like “towels”, or a code
                  like 6302.
                </span>
              </li>
            )}
            {options.map((product, i) => (
              <li
                key={product.hs6}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                // mousedown, not click: fires before the input's blur closes the list
                onMouseDown={(e) => {
                  e.preventDefault();
                  pick(product);
                }}
                onMouseEnter={() => setActive(i)}
                className={`flex cursor-pointer items-start justify-between gap-3 rounded-xl px-3 py-2.5 transition-colors ${
                  i === active ? "bg-surface-2" : ""
                }`}
              >
                <span className="min-w-0">
                  <span className="block text-sm font-medium text-fg">
                    {capitalize(product.name)}
                  </span>
                  <span className="mt-0.5 line-clamp-2 block text-xs text-muted">
                    {shortProductName(product.description)}
                  </span>
                </span>
                <span className="shrink-0 pt-0.5 text-right text-xs text-subtle tabular-nums">
                  HS {product.hs6}
                  <span className="block">
                    {product.count} {mode === "sell" ? "markets" : "suppliers"}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
      {!off && mode !== "public" && (
        <button
          type="button"
          aria-expanded={finding}
          onClick={() => setFinding((f) => !f)}
          className="inline-flex items-center gap-1 self-start text-xs text-muted underline-offset-4 hover:text-fg hover:underline"
        >
          <Sparkles className="h-3.5 w-3.5" aria-hidden /> {t("hs.notSure")}
        </button>
      )}
      {finding && !off && mode !== "public" && (
        <HsFinder
          initial={text}
          onPick={(product) => {
            setFinding(false);
            pick({ ...product, count: 0 });
          }}
        />
      )}
    </div>
  );
}
