"use client";

import { ChevronDown, Monitor, Smartphone, Tablet } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import type { VisitOut } from "@/lib/api/admin";
import { timeAgo } from "@/lib/time";

// ---------- formatting ----------
export const n = (value: number) => value.toLocaleString("en");

export const shortDay = (iso: string) =>
  new Date(`${iso.slice(0, 10)}T00:00:00Z`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });

export const dateTime = (iso: string) =>
  new Date(iso).toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

/** 42 -> "42s", 192 -> "3m 12s", 3900 -> "1h 5m". */
export function duration(seconds: number): string {
  const s = Math.round(seconds);
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m${s % 60 ? ` ${s % 60}s` : ""}`;
  const m = Math.floor((s % 3600) / 60);
  return `${Math.floor(s / 3600)}h${m ? ` ${m}m` : ""}`;
}

let regions: Intl.DisplayNames | undefined;
/** "PK" -> "Pakistan"; empty/unknown -> "Unknown". */
export function countryName(code: string | null | undefined): string {
  if (!code) return "Unknown";
  try {
    regions ??= new Intl.DisplayNames(["en"], { type: "region" });
    return regions.of(code) ?? code;
  } catch {
    return code;
  }
}

export const ago = (iso: string | null | undefined) => (iso ? timeAgo(iso) : "never");

// ---------- section tabs ----------
const SECTIONS = [
  { href: "/app/admin", label: "Overview" },
  { href: "/app/admin/visitors", label: "Visitors" },
  { href: "/app/admin/users", label: "Users" },
];

export function AdminTabs() {
  const path = usePathname();
  const current = (href: string) =>
    href === "/app/admin" ? path === href : path === href || path.startsWith(`${href}/`);
  return (
    <nav aria-label="Admin sections" className="flex gap-1 overflow-x-auto border-b border-line">
      {SECTIONS.map((s) => (
        <Link
          key={s.href}
          href={s.href}
          aria-current={current(s.href) ? "page" : undefined}
          className={`-mb-px shrink-0 border-b-2 px-3 py-2.5 text-sm transition-colors duration-150 ${
            current(s.href)
              ? "border-brand font-medium text-fg"
              : "border-transparent text-muted hover:border-line-strong hover:text-fg"
          }`}
        >
          {s.label}
        </Link>
      ))}
    </nav>
  );
}

// ---------- ranked bars ----------
export function Ranked({
  rows,
  unit,
  label = (name) => name,
}: {
  rows: { name: string; count: number }[];
  unit: string;
  label?: (name: string) => string;
}) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  if (!rows.length) return <p className="text-sm text-muted">Nothing yet.</p>;
  return (
    <ul className="flex flex-col gap-2.5">
      {rows.map((r) => (
        <li key={r.name} className="flex flex-col gap-1">
          <span className="flex items-baseline justify-between gap-3 text-sm">
            <span className="min-w-0 truncate text-fg">{label(r.name)}</span>
            <span className="shrink-0 text-muted tabular-nums">
              {n(r.count)} <span className="sr-only">{unit}</span>
            </span>
          </span>
          <span aria-hidden className="block h-1.5 rounded-full bg-surface-2">
            <span
              className="block h-full rounded-full bg-brand/60"
              style={{ width: `${(r.count / max) * 100}%` }}
            />
          </span>
        </li>
      ))}
    </ul>
  );
}

// ---------- one visit ----------
const DEVICE_ICON = { mobile: Smartphone, tablet: Tablet, desktop: Monitor } as const;

/** A visit as a row: who/where/how, then the pages in order (opens on click). */
export function VisitRow({ visit, showUser = true }: { visit: VisitOut; showUser?: boolean }) {
  const Device = DEVICE_ICON[visit.device as keyof typeof DEVICE_ICON] ?? Monitor;
  return (
    <details className="group border-b border-line last:border-0">
      <summary className="flex cursor-pointer list-none flex-col gap-1.5 px-4 py-3 hover:bg-surface-2 sm:px-5 [&::-webkit-details-marker]:hidden">
        <span className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-sm">
          {visit.live && <Badge tone="positive">Live</Badge>}
          <span className="font-medium text-fg">{countryName(visit.country)}</span>
          <span className="text-subtle">·</span>
          <span className="text-muted">
            from <span className="text-fg">{visit.source}</span>
            {visit.utm_campaign && <> ({visit.utm_campaign})</>}
          </span>
          {showUser &&
            (visit.user ? (
              <Link
                href={`/app/admin/users/${visit.user.id}`}
                onClick={(e) => e.stopPropagation()}
                className="min-w-0 truncate text-brand hover:underline"
              >
                {visit.user.full_name}
                {visit.user.is_test && " (test)"}
              </Link>
            ) : (
              <span className="text-subtle">anonymous</span>
            ))}
          <ChevronDown
            aria-hidden
            className="ml-auto h-4 w-4 shrink-0 text-subtle transition-transform group-open:rotate-180"
          />
        </span>
        <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted tabular-nums">
          <span title={dateTime(visit.started_at)}>{timeAgo(visit.started_at)}</span>
          <span className="inline-flex items-center gap-1">
            <Device aria-hidden className="h-3.5 w-3.5" />
            {visit.browser} on {visit.os}
          </span>
          <span>
            {visit.pages} {visit.pages === 1 ? "page" : "pages"}
          </span>
          <span>{duration(visit.engaged_seconds)} engaged</span>
          <span className="min-w-0 truncate">landed on {visit.landing}</span>
        </span>
      </summary>
      <ol className="mx-4 mb-3 flex flex-col gap-1 rounded-xl bg-surface-2 p-3 text-xs sm:mx-5">
        {visit.journey.map((page, i) => (
          <li key={`${page.at}-${i}`} className="flex min-w-0 items-baseline gap-3">
            <span className="w-12 shrink-0 text-subtle tabular-nums">
              {new Date(page.at).toLocaleTimeString("en-GB", {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
            <span className="min-w-0 flex-1 truncate font-mono text-fg">{page.path}</span>
            <span className="shrink-0 text-muted tabular-nums">
              {page.seconds ? duration(page.seconds) : "–"}
            </span>
          </li>
        ))}
        {visit.referrer && <li className="mt-1 text-subtle">Referred by {visit.referrer}</li>}
      </ol>
    </details>
  );
}
