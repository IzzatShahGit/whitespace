"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  BarChart3,
  FileText,
  Lock,
  MousePointerClick,
  UserPlus,
  Users,
} from "lucide-react";
import { useState } from "react";

import { Card, CardHeader, Page, PageHeader } from "@/components/ui/card";
import { EmptyState, Skeleton } from "@/components/ui/empty";
import { Stat } from "@/components/ui/stat";
import { LoadError } from "@/components/markets/load-error";
import { api } from "@/lib/api/client";
import { isMissing, unwrap } from "@/lib/api/queries";
import type { components } from "@/lib/api/schema";

type Stats = components["schemas"]["AdminStats"];
type Day = components["schemas"]["DayStats"];

const n = (value: number) => value.toLocaleString("en");
const shortDay = (iso: string) =>
  new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });

/** Page views per day: one series, thin bars, a tooltip per bar, and a table view. */
function DailyChart({ days }: { days: Day[] }) {
  const [active, setActive] = useState<number | null>(null);
  const max = Math.max(1, ...days.map((d) => d.page_views));
  const shown = active !== null ? days[active] : undefined;
  return (
    <div>
      <div className="relative">
        <div
          role="img"
          aria-label={`Page views per day, ${shortDay(days[0]!.day)} to ${shortDay(days.at(-1)!.day)}, peak ${n(max)}`}
          className="flex h-40 items-end gap-0.5 border-b border-line"
          onMouseLeave={() => setActive(null)}
        >
          {days.map((d, i) => (
            <button
              key={d.day}
              type="button"
              aria-label={`${shortDay(d.day)}: ${n(d.page_views)} page views, ${n(d.visitors)} visitors, ${n(d.sign_ups)} sign-ups`}
              onMouseEnter={() => setActive(i)}
              onFocus={() => setActive(i)}
              onBlur={() => setActive(null)}
              className="group flex h-full min-w-0 flex-1 items-end outline-none"
            >
              <span
                className={`block w-full rounded-t-[4px] transition-colors ${
                  active === i ? "bg-brand" : "bg-brand/70 group-focus-visible:bg-brand"
                }`}
                style={{
                  height: d.page_views ? `${Math.max((d.page_views / max) * 100, 2)}%` : "0",
                }}
              />
            </button>
          ))}
        </div>
        {shown && active !== null && (
          <div
            role="status"
            className="pointer-events-none absolute -top-2 z-10 -translate-y-full rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-card"
            style={{
              left: `${((active + 0.5) / days.length) * 100}%`,
              transform: `translate(${active > days.length / 2 ? "-100%" : "0"}, -100%)`,
            }}
          >
            <p className="font-medium text-fg">{shortDay(shown.day)}</p>
            <p className="text-muted tabular-nums">
              {n(shown.page_views)} views · {n(shown.visitors)} visitors · {n(shown.sign_ups)}{" "}
              sign-ups
            </p>
          </div>
        )}
      </div>
      <div className="mt-1.5 flex justify-between text-xs text-subtle tabular-nums">
        <span>{shortDay(days[0]!.day)}</span>
        <span>{shortDay(days.at(-1)!.day)}</span>
      </div>
      <details className="mt-4 text-sm">
        <summary className="cursor-pointer text-muted hover:text-fg">Show as a table</summary>
        <table className="mt-3 w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-subtle">
              <th scope="col" className="pb-2 font-medium">
                Day
              </th>
              <th scope="col" className="pb-2 text-right font-medium">
                Page views
              </th>
              <th scope="col" className="pb-2 text-right font-medium">
                Visitors
              </th>
              <th scope="col" className="pb-2 text-right font-medium">
                Sign-ups
              </th>
            </tr>
          </thead>
          <tbody className="border-t border-line">
            {[...days].reverse().map((d) => (
              <tr key={d.day} className="text-muted">
                <td className="py-1">{shortDay(d.day)}</td>
                <td className="py-1 text-right tabular-nums">{n(d.page_views)}</td>
                <td className="py-1 text-right tabular-nums">{n(d.visitors)}</td>
                <td className="py-1 text-right tabular-nums">{n(d.sign_ups)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}

function Ranked({ rows, unit }: { rows: { name: string; count: number }[]; unit: string }) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  if (!rows.length) return <p className="text-sm text-muted">Nothing yet.</p>;
  return (
    <ul className="flex flex-col gap-2.5">
      {rows.map((r) => (
        <li key={r.name} className="flex flex-col gap-1">
          <span className="flex items-baseline justify-between gap-3 text-sm">
            <span className="min-w-0 truncate text-fg">{r.name}</span>
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

/** Usage over the last 30 days, from our own anonymous counts. Admins only. */
export function AdminView() {
  const stats = useQuery({
    queryKey: ["admin-stats"],
    queryFn: () => unwrap(api.GET("/api/v1/admin/stats")),
    retry: false,
    staleTime: 60_000,
  });

  if (stats.isPending) {
    return (
      <Page>
        <Skeleton className="h-24" />
        <Skeleton className="h-64" />
      </Page>
    );
  }
  if (!stats.data) {
    return (
      <Page>
        {isMissing(stats.error) ? (
          <EmptyState icon={<Lock />} title="Not available">
            This page is for the site’s admins.
          </EmptyState>
        ) : (
          <LoadError title="Couldn’t load usage" onRetry={() => void stats.refetch()} />
        )}
      </Page>
    );
  }
  const s: Stats = stats.data;
  const t = s.totals;
  return (
    <Page>
      <PageHeader
        title="Usage"
        description={`${shortDay(s.since)} – ${shortDay(s.until)}. Anonymous counts: no cookies, no addresses.`}
      />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat
          label="Visitors"
          icon={<Users />}
          value={n(t.visitors)}
          note={`${n(t.page_views)} page views`}
          explain="Unique per day; the same person on two days counts twice."
        />
        <Stat label="Sign-ups" icon={<UserPlus />} value={n(t.sign_ups)} note="last 30 days" />
        <Stat
          label="Active users"
          icon={<Activity />}
          value={n(t.active_7d)}
          note="signed in, last 7 days"
        />
        <Stat label="All accounts" icon={<FileText />} value={n(t.users)} />
      </div>
      <Card className="p-5 sm:p-6">
        <CardHeader
          icon={<BarChart3 />}
          title="Page views per day"
          description="Hover or tab through a bar for visitors and sign-ups."
        />
        <div className="mt-6">
          <DailyChart days={s.days} />
        </div>
      </Card>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-5 sm:p-6">
          <CardHeader
            icon={<FileText />}
            title="Top pages"
            description="Ids and products are grouped."
          />
          <div className="mt-5">
            <Ranked rows={s.top_pages} unit="views" />
          </div>
        </Card>
        <Card className="p-5 sm:p-6">
          <CardHeader
            icon={<MousePointerClick />}
            title="Features used"
            description="Last 30 days, all users."
          />
          <div className="mt-5">
            <Ranked rows={[...s.actions].sort((a, b) => b.count - a.count)} unit="times" />
          </div>
        </Card>
      </div>
    </Page>
  );
}
