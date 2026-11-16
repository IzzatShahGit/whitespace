"use client";

import { CalendarClock, CloudOff } from "lucide-react";

import { LoadError } from "@/components/markets/load-error";
import { MonthlyChart } from "@/components/markets/monthly-chart";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/empty";
import { useRecentMovement } from "@/lib/api/queries";
import { monthLabel, percent, points, signedPercent } from "@/lib/format";

function Figure({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-xl bg-surface-2/60 p-3.5">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-1 text-xl font-semibold tracking-tight tabular-nums">{value}</dd>
      {note && <dd className="mt-0.5 text-xs text-muted">{note}</dd>}
    </div>
  );
}

/**
 * What changed after the annual data ends: monthly customs data for EU and US markets.
 * Shown beside the ranking; it never changes the score. Renders nothing for markets
 * without a monthly source.
 */
export function RecentPanel({
  exporter,
  exporterName,
  hs6,
  market,
  annualEndYear,
}: {
  exporter: string;
  exporterName: string;
  hs6: string;
  market: string;
  annualEndYear: number;
}) {
  const recent = useRecentMovement(exporter, hs6, market);

  if (recent.data === null) return null; // no monthly source for this market
  if (recent.isError) {
    return (
      <LoadError
        title="Couldn’t load the monthly figures"
        onRetry={() => void recent.refetch()}
        retrying={recent.isFetching}
      >
        {recent.error.message}
      </LoadError>
    );
  }
  if (!recent.data) {
    return (
      <Card className="flex flex-col gap-5 p-5 sm:p-6" aria-busy>
        <Skeleton className="h-10 w-72 max-w-full" />
        <div className="grid gap-3 sm:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
        <Skeleton className="h-56" />
      </Card>
    );
  }

  const d = recent.data;
  const change = d.change_12m;
  const title =
    change === null
      ? `Monthly imports since ${annualEndYear}`
      : Math.abs(change) < 0.005
        ? "Imports held steady over the last 12 months"
        : `Imports ${change > 0 ? "up" : "down"} ${Math.round(Math.abs(change) * 100)}% in the last 12 months`;

  return (
    <Card className="p-5 sm:p-6">
      <CardHeader
        icon={<CalendarClock />}
        title={title}
        description={`Monthly customs data to ${monthLabel(d.latest_month)}, newer than the ${annualEndYear} ranking. It doesn’t change the score.`}
        action={
          d.stale ? (
            <Badge tone="caution" icon={<CloudOff />}>
              Saved copy
            </Badge>
          ) : undefined
        }
      />
      {d.stale && (
        <p className="mt-3 text-xs text-muted">
          The source couldn’t be reached, so this is the last copy we saved.
        </p>
      )}

      <dl className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Figure
          label="Imports, last 12 months"
          value={change === null ? "—" : signedPercent(change)}
          note="vs the 12 months before"
        />
        <Figure
          label={`${exporterName}’s share`}
          value={percent(d.exporter_share_recent, { floor: true })}
          note={
            d.exporter_share_before === null
              ? "last 12 months"
              : `${points(d.exporter_share_recent - d.exporter_share_before)} vs the year before`
          }
        />
        <div className="col-span-2 sm:col-span-1">
          <Figure label="Latest month" value={monthLabel(d.latest_month)} note={d.source} />
        </div>
      </dl>

      <div className="mt-6">
        <MonthlyChart data={d} exporterName={exporterName} />
      </div>

      {d.suppliers.length > 0 && (
        <div className="mt-6">
          <h3 className="text-sm font-semibold">Largest suppliers, last 12 months</h3>
          <ul className="mt-2 divide-y divide-line/70">
            {d.suppliers.map((s) => {
              const you = s.name === exporterName;
              return (
                <li
                  key={s.name}
                  className="grid grid-cols-[minmax(0,1fr)_minmax(0,6rem)_3rem_4rem] items-center gap-3 py-2 text-sm"
                >
                  <span className={`truncate ${you ? "font-medium text-accent-strong" : ""}`}>
                    {s.name}
                  </span>
                  <span aria-hidden className="h-1.5 overflow-hidden rounded-full bg-surface-2">
                    <span
                      className="block h-full rounded-full"
                      style={{
                        width: `${Math.min(100, s.share_recent * 100)}%`,
                        background: you ? "var(--chart-exporter)" : "var(--chart-end)",
                      }}
                    />
                  </span>
                  <span className="text-right font-medium tabular-nums">
                    {percent(s.share_recent, { floor: true })}
                  </span>
                  <span className="text-right text-xs text-subtle tabular-nums">
                    {s.share_before !== null ? points(s.share_recent - s.share_before) : ""}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {d.note && (
        <p className="mt-5 rounded-xl bg-surface-2/60 px-3.5 py-2.5 text-xs leading-5 text-muted">
          {d.note}
        </p>
      )}
      <p className="mt-3 text-xs text-subtle">
        Source: {d.source}, values in {d.currency}. Measured monthly.
      </p>
    </Card>
  );
}
