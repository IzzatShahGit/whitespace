"use client";

import { type KeyboardEvent, type ReactNode, useRef } from "react";

export type SegmentedItem<T extends string> = { value: T; label: ReactNode; icon?: ReactNode };

/**
 * A row of mutually exclusive pills (sort orders, filters): a radio group with arrow-key
 * movement. Scrolls sideways on narrow screens instead of wrapping.
 */
export function Segmented<T extends string>({
  items,
  value,
  onChange,
  label,
}: {
  items: SegmentedItem<T>[];
  value: T;
  onChange: (value: T) => void;
  label: string;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const step =
      e.key === "ArrowRight" || e.key === "ArrowDown"
        ? 1
        : e.key === "ArrowLeft" || e.key === "ArrowUp"
          ? -1
          : 0;
    if (!step) return;
    e.preventDefault();
    const index = items.findIndex((i) => i.value === value);
    const next = (index + step + items.length) % items.length;
    onChange(items[next].value);
    refs.current[next]?.focus();
  }

  return (
    <div
      role="radiogroup"
      aria-label={label}
      onKeyDown={onKeyDown}
      className="-mx-1 flex gap-1.5 overflow-x-auto px-1 py-1"
    >
      {items.map((item, i) => {
        const selected = item.value === value;
        return (
          <button
            key={item.value}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="radio"
            aria-checked={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(item.value)}
            className={`inline-flex min-h-9 shrink-0 items-center gap-1.5 rounded-full border px-3.5 text-sm transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand [&>svg]:h-4 [&>svg]:w-4 ${
              selected
                ? "border-brand bg-brand-soft font-medium text-brand"
                : "border-line bg-surface text-muted hover:border-line-strong hover:text-fg"
            }`}
          >
            {item.icon}
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
