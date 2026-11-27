"use client";

import {
  Activity,
  BarChart3,
  Compass,
  FileText,
  Globe2,
  Lock,
  MonitorSmartphone,
  MousePointerClick,
  Radio,
  Users,
} from "lucide-react";
import { useState } from "react";

import { AdminTabs, countryName, duration, n, Ranked, shortDay } from "@/components/admin/parts";
import { LoadError } from "@/components/markets/load-error";
import { Card, CardHeader, Page, PageHeader } from "@/components/ui/card";
import { EmptyState, Skeleton } from "@/components/ui/empty";
import { Segmented } from "@/components/ui/segmented";
import { Stat, StatGroup } from "@/components/ui/stat";
import { type AdminStats, useAdminStats } from "@/lib/api/admin";
import { isMissing } from "@/lib/api/queries";

type Day = AdminStats["days"][number];
type Metric = "visits" | "active_users" | "sign_ups" | "page_views";
const METRICS: { value: Metric; label: string; unit: string }[] = [
  { value: "visits", label: "Visits", unit: "visits" },
  { value: "active_users", label: "Active users", unit: "active users" },
  { value: "sign_ups", label: "Sign-ups", unit: "sign-ups" },
  { value: "page_views", label: "Page views", unit: "page views" },
];

/** One series per day: thin bars, a tooltip per bar, and a table view. */
function DailyChart({ days, metric }: { days: Day[]; metric: Metric }) {
  const [active, setActive] = useState<number | null>(null);
  const unit = METRICS.find((m) => m.value === metric)!.unit;
  const max = Math.max(1, ...days.map((d) => d[metric]));
  const shown = active !== null ? days[active] : undefined;
  return (
    <div>
      <div className="relative">
        <div
          role="img"
          aria-label={`${unit} per day, ${shortDay(days[0]!.day)} to ${shortDay(days.at(-1)!.day)}, peak ${n(max)}`}
          className="flex h-40 items-end gap-0.5 border-b border-line"
          onMouseLeave={() => setActive(null)}
        >
          {days.map((d, i) => (
            <button
              key={d.day}
              type="button"
              aria-label={`${shortDay(d.day)}: ${n(d[metric])} ${unit}`}
              onMouseEnter={() => setActive(i)}
              onFocus={() => setActive(i)}
              onBlur={() => setActive(null)}
              className="group flex h-full min-w-0 flex-1 items-end outline-none"
            >
              <span
                className={`block w-full rounded-t-[4px] transition-colors ${
                  active === i ? "bg-brand" : "bg-brand/70 group-focus-visible:bg-brand"
                }`}
                style={{ height: d[metric] ? `${Math.max((d[metric] / max) * 100, 2)}%` : "0" }}
              />
            </button>
          ))}
        </div>
        {shown && active !== null && (
          <div
            role="status"
            className="pointer-events-none absolute -top-2 z-10 rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-card"
            style={{
              left: `${((active + 0.5) / days.length) * 100}%`,
              transform: `translate(${active > days.length / 2 ? "-100%" : "0"}, -100%)`,
            }}
          >
            <p className="font-medium text-fg">{shortDay(shown.day)}</p>
            <p className="text-muted tabular-nums">
              {n(shown.visits)} visits · {n(shown.active_users)} active · {n(shown.sign_ups)}{" "}
              sign-ups · {n(shown.page_views)} views
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
        <div className="overflow-x-auto">
          <table className="mt-3 w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-subtle">
                <th scope="col" className="pb-2 font-medium">
                  Day
                </th>
                {METRICS.map((m) => (
                  <th key={m.value} scope="col" className="pb-2 text-right font-medium">
                    {m.label}
                  </th>
                ))}
                <th scope="col" className="pb-2 text-right font-medium">
                  Visitors
                </th>
              </tr>
            </thead>
            <tbody className="border-t border-line">
              {[...days].reverse().map((d) => (
                <tr key={d.day} className="text-muted">
                  <td className="py-1">{shortDay(d.day)}</td>
                  {METRICS.map((m) => (
                    <td key={m.value} className="py-1 text-right tabular-nums">
                      {n(d[m.value])}
                    </td>
                  ))}
                  <td className="py-1 text-right tabular-nums">{n(d.visitors)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}

/** The platform at a glance: last 30 days, real users only. Admins only. */
export function AdminView() {
  const stats = useAdminStats();
  const [metric, setMetric] = useState<Metric>("visits");

  if (stats.isPending) {
    return (
      <Page>
        <Skeleton className="h-10" />
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
  const s = stats.data;
  const t = s.totals;
  const v = s.visits;
  return (
    <Page>
      <PageHeader
        title="Admin"
        description={`${shortDay(s.since)} – ${shortDay(s.until)}. Test, demo and admin accounts are left out of these numbers.`}
      />
      <AdminTabs />
      <StatGroup>
        <Stat
          label="On the site now"
          icon={<Radio />}
          value={n(v.live_now)}
          note="active in the last 5 minutes"
        />
        <Stat
          label="Visitors"
          icon={<Users />}
          value={n(t.visitors)}
          note={`${n(v.visits)} visits · ${n(t.page_views)} page views`}
          explain="Unique per day; the same anonymous person on two days counts twice."
        />
        <Stat
          label="Real users"
          icon={<FileText />}
          value={n(t.users)}
          note={`+${n(t.sign_ups)} in 30 days · ${n(t.test_users)} test/demo`}
        />
        <Stat
          label="Active users"
          icon={<Activity />}
          value={n(t.active_7d)}
          note={`last 7 days · ${n(t.active_30d)} in 30 days`}
          explain="Real accounts that used the app (signed in, or a session renewed)."
        />
      </StatGroup>

      <Card className="p-5 sm:p-6">
        <CardHeader
          icon={<BarChart3 />}
          title="Per day"
          description="Hover or tab through a bar for that day’s numbers."
        />
        <div className="mt-4">
          <Segmented items={METRICS} value={metric} onChange={setMetric} label="Show per day" />
        </div>
        <div className="mt-6">
          <DailyChart days={s.days} metric={metric} />
        </div>
      </Card>

      <StatGroup>
        <Stat
          label="Time per visit"
          value={duration(v.avg_seconds)}
          note="engaged, on average"
          explain="Counted while the tab is in front and someone moved, typed or scrolled in the last 2 minutes."
        />
        <Stat label="Pages per visit" value={v.avg_pages.toFixed(1)} />
        <Stat
          label="Left after one page"
          value={`${Math.round(v.bounce_rate * 100)}%`}
          note="one page, under 10 s"
        />
        <Stat
          label="Signed-in visits"
          value={n(v.signed_in)}
          note={v.visits ? `${Math.round((v.signed_in / v.visits) * 100)}% of visits` : undefined}
        />
      </StatGroup>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="p-5 sm:p-6">
          <CardHeader icon={<Globe2 />} title="Countries" description="Where visits come from." />
          <div className="mt-5">
            <Ranked rows={v.countries} unit="visits" label={countryName} />
          </div>
        </Card>
        <Card className="p-5 sm:p-6">
          <CardHeader
            icon={<Compass />}
            title="Sources"
            description="The site or link that sent them."
          />
          <div className="mt-5">
            <Ranked rows={v.sources} unit="visits" />
          </div>
        </Card>
        <Card className="p-5 sm:p-6">
          <CardHeader icon={<MonitorSmartphone />} title="Devices" description="And browsers." />
          <div className="mt-5 flex flex-col gap-6">
            <Ranked
              rows={v.devices}
              unit="visits"
              label={(d) => d.charAt(0).toUpperCase() + d.slice(1)}
            />
            <Ranked rows={v.browsers} unit="visits" />
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="p-5 sm:p-6">
          <CardHeader
            icon={<FileText />}
            title="Landing pages"
            description="The first page of a visit."
          />
          <div className="mt-5">
            <Ranked rows={v.landing} unit="visits" />
          </div>
        </Card>
        <Card className="p-5 sm:p-6">
          <CardHeader
            icon={<FileText />}
            title="Top pages"
            description="Ids and products grouped."
          />
          <div className="mt-5">
            <Ranked rows={s.top_pages} unit="views" />
          </div>
        </Card>
        <Card className="p-5 sm:p-6">
          <CardHeader
            icon={<MousePointerClick />}
            title="Features used"
            description="Last 30 days, all accounts."
          />
          <div className="mt-5">
            <Ranked rows={[...s.actions].sort((a, b) => b.count - a.count)} unit="times" />
          </div>
        </Card>
      </div>
    </Page>
  );
}
