"use client";

import { type KeyboardEvent, useId, useState } from "react";

import { type ProductMatch, useProductSearch } from "@/lib/api/queries";
import { shortProductName } from "@/lib/format";
import { useDebounced } from "@/lib/use-debounced";

/**
 * Search-as-you-type for products, as an accessible combobox
 * (arrow keys, Enter to pick, Escape to close).
 */
export function ProductPicker({
  exporter,
  onSelect,
  exclude = [],
  placeholder = "Describe your product, e.g. cotton towels",
  disabled = false,
}: {
  exporter: string | undefined;
  onSelect: (product: ProductMatch) => void;
  exclude?: string[];
  placeholder?: string;
  disabled?: boolean;
}) {
  const listId = useId();
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const query = useDebounced(text);
  const search = useProductSearch(exporter, query);

  const options = (search.data ?? []).filter((p) => !exclude.includes(p.hs6));
  const showList = open && query.trim().length >= 2;
  const waiting = search.isFetching && !search.data;

  function pick(product: ProductMatch) {
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
    <div className="relative">
      <input
        type="search"
        role="combobox"
        aria-expanded={showList}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={showList && options[active] ? `${listId}-${active}` : undefined}
        value={text}
        disabled={disabled || !exporter}
        placeholder={placeholder}
        onChange={(e) => {
          setText(e.target.value);
          setOpen(true);
          setActive(0);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
        className="h-12 w-full rounded-xl border border-ink-line bg-ink-raised px-4 text-cream transition-colors outline-none placeholder:text-sage-dim/70 focus:border-ember/70 focus:ring-2 focus:ring-ember/20 disabled:opacity-50"
      />
      {showList && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-30 mt-2 max-h-80 w-full overflow-auto rounded-xl border border-ink-line bg-ink-raised p-1 shadow-[0_20px_40px_-20px_rgba(0,0,0,0.7)]"
        >
          {waiting && <li className="px-3 py-2.5 text-sm text-sage-dim">Searching…</li>}
          {!waiting && options.length === 0 && (
            <li className="px-3 py-2.5 text-sm text-sage-dim">
              No products match. Try simpler words like “towels”, or a code like 6302.
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
              className={`cursor-pointer rounded-lg px-3 py-2.5 ${i === active ? "bg-ink-line/60" : ""}`}
            >
              <p className="text-sm text-cream">{shortProductName(product.description)}</p>
              <p className="mt-0.5 text-xs text-sage-dim">
                HS {product.hs6} · {product.markets} ranked markets
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
