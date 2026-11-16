"use client";

import { type KeyboardEvent, type ReactNode, useId, useRef } from "react";

export type TabItem<T extends string> = { value: T; label: ReactNode; icon?: ReactNode };

/** Accessible tabs (arrow keys move between them). The caller owns the selected value. */
export function Tabs<T extends string>({
  items,
  value,
  onChange,
  label,
}: {
  items: TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
  label: string;
}) {
  const id = useId();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const index = items.findIndex((i) => i.value === value);
    const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const next = (index + step + items.length) % items.length;
    onChange(items[next].value);
    refs.current[next]?.focus();
  }

  return (
    <div
      role="tablist"
      aria-label={label}
      onKeyDown={onKeyDown}
      className="flex gap-1 overflow-x-auto rounded-xl border border-line bg-surface-2/60 p-1"
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
            role="tab"
            id={`${id}-${item.value}`}
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(item.value)}
            className={`flex shrink-0 items-center gap-2 rounded-lg px-3.5 py-2 text-sm transition-all duration-200 [&>svg]:h-4 [&>svg]:w-4 ${
              selected ? "bg-surface font-medium text-fg shadow-card" : "text-muted hover:text-fg"
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
