"use client";

import { MonthlyChart } from "@/components/markets/monthly-chart";
import { Button } from "@/components/ui/button";
import { useRecentMovement } from "@/lib/api/queries";
import { monthLabel, percent, points, signedPercent } from "@/lib/format";

function Tile({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-xl border border-ink-line p-4">
      <p className="text-xs text-sage-dim">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums">{value}</p>
      {note && <p className="mt-0.5 text-xs text-sage">{note}</p>}
    </div>
  );
}

/**
 * What changed after the annual data ends: monthly customs data for EU and US
 * markets. Shown beside the ranking; it never changes the score. Renders nothing
 * for markets without a monthly source.
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
  return (
    <section className="rounded-2xl border border-ink-line bg-ink-raised p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 className="text-lg font-medium">Since {annualEndYear}: monthly data</h2>
          <p className="text-sm text-sage">Newer than the ranking, for a read on recent shifts.</p>
        </div>
        {recent.data?.stale && (
          <span className="rounded-full border border-ink-line px-2.5 py-0.5 text-xs text-sage">
            Source unreachable: showing the last saved copy
          </span>
        )}
      </div>

      {recent.isPending && (
        <div className="mt-6 grid animate-pulse gap-3 sm:grid-cols-3" aria-label="Loading">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-20 rounded-xl bg-ink-line/40" />
          ))}
        </div>
      )}

      {recent.isError && (
        <div className="mt-5 flex flex-wrap items-center gap-4">
          <p className="text-sm text-sage">{recent.error.message}</p>
          <Button variant="secondary" className="h-9 px-4" onClick={() => recent.refetch()}>
            Try again
          </Button>
        </div>
      )}

      {recent.data && (
        <>
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <Tile
              label="Imports, last 12 months"
              value={recent.data.change_12m === null ? "—" : signedPercent(recent.data.change_12m)}
              note="vs the 12 months before"
            />
            <Tile
              label={`${exporterName}'s share`}
              value={percent(recent.data.exporter_share_recent, { floor: true })}
              note={
                recent.data.exporter_share_before === null
                  ? "last 12 months"
                  : `${points(recent.data.exporter_share_recent - recent.data.exporter_share_before)} vs the year before`
              }
            />
            <Tile
              label="Latest month"
              value={monthLabel(recent.data.latest_month)}
              note={recent.data.source}
            />
          </div>

          <div className="mt-6">
            <MonthlyChart data={recent.data} exporterName={exporterName} />
          </div>

          {recent.data.suppliers.length > 0 && (
            <div className="mt-6">
              <h3 className="text-sm font-medium">Largest suppliers, last 12 months</h3>
              <ul className="mt-2 divide-y divide-ink-line/60 text-sm">
                {recent.data.suppliers.map((s) => (
                  <li key={s.name} className="flex items-center justify-between py-2">
                    <span>{s.name}</span>
                    <span className="text-sage tabular-nums">
                      {percent(s.share_recent, { floor: true })}
                      {s.share_before !== null && (
                        <span className="ml-2 text-sage-dim">
                          ({points(s.share_recent - s.share_before)})
                        </span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {recent.data.note && (
            <p className="mt-5 rounded-lg bg-ink px-3 py-2 text-xs leading-5 text-sage">
              {recent.data.note}
            </p>
          )}
          <p className="mt-3 text-xs text-sage-dim">
            Source: {recent.data.source}, values in {recent.data.currency}. Measured, monthly. Shown
            beside the ranking: it does not change the score.
          </p>
        </>
      )}
    </section>
  );
}
