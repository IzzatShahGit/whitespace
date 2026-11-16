"use client";

import {
  ArrowRight,
  CornerDownLeft,
  PackageSearch,
  Search,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { type KeyboardEvent, type ReactNode, useEffect, useRef, useState } from "react";

import { NAV, SETTINGS } from "@/components/shell/nav";
import { useProductSearch, useProfile } from "@/lib/api/queries";
import { capitalize } from "@/lib/format";
import { useDebounced } from "@/lib/use-debounced";

type Result = { key: string; icon: ReactNode; title: string; detail: string; href: string };

const OPEN_EVENT = "ws-open-search";

/** Open the search from anywhere (e.g. the top bar's search button). */
export function openSearch() {
  window.dispatchEvent(new Event(OPEN_EVENT));
}

/**
 * ⌘K / Ctrl+K: one box to jump anywhere — a section, a product to sell or buy, or a
 * question for the guide.
 */
export function CommandPalette() {
  const router = useRouter();
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");
  const [active, setActive] = useState(0);
  const query = useDebounced(text, 200).trim();
  const profile = useProfile();
  const exporter = profile.data?.exporter.code;
  const sell = useProductSearch("sell", exporter, query);
  const buy = useProductSearch("buy", exporter, query);

  useEffect(() => {
    function open() {
      setText("");
      setActive(0);
      dialog.current?.showModal();
      requestAnimationFrame(() => input.current?.focus());
    }
    function onKey(e: globalThis.KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (dialog.current?.open) dialog.current.close();
        else open();
      }
    }
    window.addEventListener("keydown", onKey);
    window.addEventListener(OPEN_EVENT, open);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener(OPEN_EVENT, open);
    };
  }, []);

  const lower = query.toLowerCase();
  const sections = [...NAV, SETTINGS].filter(
    (n) => !lower || n.label.toLowerCase().includes(lower) || n.hint.toLowerCase().includes(lower),
  );
  const results: Result[] = [
    ...(query.length >= 2
      ? [
          {
            key: "ask",
            icon: <Sparkles className="h-4 w-4 text-accent" />,
            title: `Ask Whitespace: “${query}”`,
            detail: "Get an answer from the data",
            href: `/app/ask?q=${encodeURIComponent(query)}`,
          },
        ]
      : []),
    ...(query.length >= 2 ? (sell.data ?? []).slice(0, 4) : []).map((p) => ({
      key: `sell-${p.hs6}`,
      icon: <TrendingUp className="h-4 w-4 text-brand" />,
      title: `Sell ${p.name}`,
      detail: `${p.count} ranked markets · HS ${p.hs6}`,
      href: `/app/markets/${p.hs6}`,
    })),
    ...(query.length >= 2 ? (buy.data ?? []).slice(0, 3) : []).map((p) => ({
      key: `buy-${p.hs6}`,
      icon: <PackageSearch className="h-4 w-4 text-brand" />,
      title: `Buy ${p.name}`,
      detail: `${p.count} supplier countries · HS ${p.hs6}`,
      href: `/app/buy/${p.hs6}`,
    })),
    ...sections.map(({ href, label, hint, icon: Icon }) => ({
      key: href,
      icon: <Icon className="h-4 w-4 text-subtle" />,
      title: capitalize(label),
      detail: hint,
      href,
    })),
  ];

  function go(result: Result | undefined) {
    if (!result) return;
    dialog.current?.close();
    router.push(result.href);
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      go(results[active]);
    }
  }

  return (
    <dialog
      ref={dialog}
      aria-label="Search"
      onClick={(e) => e.target === dialog.current && dialog.current?.close()}
      className="m-auto mt-[12vh] w-[min(40rem,calc(100vw-2rem))] overflow-hidden rounded-3xl border border-line bg-surface p-0 text-fg shadow-pop backdrop:bg-black/40 backdrop:backdrop-blur-sm open:animate-[pop-in_180ms_ease-out]"
    >
      <div className="flex items-center gap-3 border-b border-line px-5">
        <Search className="h-5 w-5 text-subtle" />
        <input
          ref={input}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setActive(0);
          }}
          onKeyDown={onKeyDown}
          role="combobox"
          aria-expanded
          aria-controls="palette-results"
          aria-activedescendant={results[active] ? `palette-${results[active].key}` : undefined}
          placeholder="Search products, sections, or ask a question…"
          className="h-14 flex-1 bg-transparent text-base outline-none placeholder:text-subtle"
        />
        <kbd className="rounded-md border border-line px-1.5 py-0.5 text-xs text-subtle">Esc</kbd>
      </div>
      <ul id="palette-results" role="listbox" className="max-h-[60vh] overflow-auto p-2">
        {results.map((r, i) => (
          <li
            key={r.key}
            id={`palette-${r.key}`}
            role="option"
            aria-selected={i === active}
            onMouseEnter={() => setActive(i)}
            onClick={() => go(r)}
            className={`flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 ${
              i === active ? "bg-surface-2" : ""
            }`}
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-canvas">
              {r.icon}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm">{r.title}</span>
              <span className="block truncate text-xs text-subtle">{r.detail}</span>
            </span>
            {i === active ? (
              <CornerDownLeft className="h-4 w-4 text-subtle" />
            ) : (
              <ArrowRight className="h-4 w-4 text-transparent" />
            )}
          </li>
        ))}
      </ul>
    </dialog>
  );
}
