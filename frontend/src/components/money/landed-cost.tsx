"use client";

import { CircleCheck, ExternalLink, Landmark, TriangleAlert, TrendingDown } from "lucide-react";
import { useId, useState } from "react";

import { Badge, Callout } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/empty";
import { ApiError } from "@/lib/api/queries";
import { type LandedLine, useDuties, useLandedCost } from "@/lib/api/landed-cost";
import { perKg } from "@/lib/money";

const rate = (pct: number) => `${Number(pct.toFixed(1))}%`;

/**
 * Import duty: what the exporter pays to enter this market vs its main rival, with the
 * trade scheme behind it. Hidden for markets the tariff data doesn't cover.
 */
/** The scheme's name, or what kind of rate it is when the source doesn't name one. */
function rateLabel(rate: { kind: string; scheme?: string | null }): string {
  return rate.scheme ?? (rate.kind === "preference" ? "Preferential rate" : "Standard rate");
}

export function DutyAdvantage({
  exporter,
  hs6,
  market,
  marketName,
}: {
  exporter: string;
  hs6: string;
  market: string;
  marketName: string;
}) {
  const duties = useDuties(exporter, hs6, market);

  if (duties.data === null) return null; // not covered
  if (duties.isPending) return <Skeleton className="h-48 rounded-2xl" />;
  if (duties.isError) {
    const down = duties.error instanceof ApiError && duties.error.status === 503;
    return (
      <p className="rounded-2xl border border-line bg-surface px-4 py-3 text-sm text-muted">
        {down
          ? "The tariff source isn’t answering right now, so import duties can’t be shown. Try again later."
          : "Couldn’t load import duties for this market."}
      </p>
    );
  }

  const d = duties.data;
  const rival = d.rivals.find((r) => r.country.code === d.main_rival?.code) ?? d.rivals[0];
  const adv = d.advantage_pts;
  const others = d.rivals.filter((r) => r !== rival).slice(0, 5);

  return (
    <Card className="p-5 sm:p-6">
      <CardHeader
        icon={<Landmark />}
        title={`Import duty into ${marketName}`}
        description={d.summary}
        action={
          d.stale ? (
            <Badge tone="caution">Saved copy</Badge>
          ) : adv !== null && Math.abs(adv) >= 0.5 ? (
            <Badge tone={adv > 0 ? "positive" : "negative"}>
              {adv > 0 ? `${rate(adv)} pts lower than rivals` : `${rate(-adv)} pts higher`}
            </Badge>
          ) : undefined
        }
      />

      <dl className="mt-5 grid grid-cols-2 gap-3">
        <div className="rounded-xl bg-accent-soft/60 p-3.5 sm:p-4">
          <dt className="text-xs font-medium text-accent-strong">You ({d.yours.country.name})</dt>
          <dd className="mt-1 text-2xl font-semibold tracking-tight tabular-nums">
            {rate(d.yours.rate_pct)}
          </dd>
          <dd className="mt-1.5">
            <Badge tone={d.yours.kind === "preference" ? "brand" : "neutral"}>
              {rateLabel(d.yours)}
            </Badge>
          </dd>
        </div>
        {rival ? (
          <div className="rounded-xl bg-surface-2/70 p-3.5 sm:p-4">
            <dt className="truncate text-xs font-medium text-muted">
              Main rival ({rival.country.name})
            </dt>
            <dd className="mt-1 text-2xl font-semibold tracking-tight tabular-nums">
              {rate(rival.rate_pct)}
            </dd>
            <dd className="mt-1.5">
              <Badge tone={rival.kind === "preference" ? "brand" : "neutral"}>
                {rateLabel(rival)}
              </Badge>
            </dd>
          </div>
        ) : (
          <div className="rounded-xl bg-surface-2/70 p-3.5 sm:p-4">
            <dt className="text-xs font-medium text-muted">Standard rate</dt>
            <dd className="mt-1 text-2xl font-semibold tracking-tight tabular-nums">
              {rate(d.standard.rate_pct)}
            </dd>
          </div>
        )}
      </dl>

      {others.length > 0 && (
        <p className="mt-4 text-sm text-muted">
          Other suppliers:{" "}
          {others.map((r, i) => (
            <span key={r.country.code}>
              {i > 0 && " · "}
              {r.country.name}{" "}
              <span className="font-medium text-fg tabular-nums">{rate(r.rate_pct)}</span>
            </span>
          ))}
        </p>
      )}

      <div className="mt-4 flex flex-col gap-1 text-xs leading-5 text-subtle">
        {[d.yours.note, ...d.notes].filter(Boolean).map((note) => (
          <p key={note}>{note}</p>
        ))}
        <p>
          {d.yours.source}, {d.yours.year} ·{" "}
          <a
            href={d.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 rounded underline-offset-4 hover:text-muted hover:underline focus-visible:outline-2 focus-visible:outline-brand"
          >
            Check the tariff <ExternalLink className="h-3 w-3" aria-hidden />
          </a>
        </p>
      </div>
    </Card>
  );
}

function Line({
  label,
  value,
  strong = false,
}: {
  label: string;
  value: string;
  strong?: boolean;
}) {
  return (
    <div className={`flex items-baseline justify-between gap-3 ${strong ? "font-semibold" : ""}`}>
      <dt className={strong ? "text-fg" : "text-muted"}>{label}</dt>
      <dd className="tabular-nums">{value}</dd>
    </div>
  );
}

const TONE_ICON = { positive: CircleCheck, neutral: TriangleAlert, negative: TrendingDown };
const TONE = { positive: "positive", neutral: "caution", negative: "negative" } as const;

/** Your price + freight + duty = landed cost, set against what the market pays. */
export function LandedReceipt({
  exporter,
  hs6,
  market,
  marketName,
  cost,
}: {
  exporter: string;
  hs6: string;
  market: string;
  marketName: string;
  cost: number;
}) {
  const id = useId();
  const [freightText, setFreightText] = useState("");
  const parsed = Number(freightText);
  const freight = freightText.trim() && parsed >= 0 && parsed <= 100 ? parsed : null;
  const duties = useDuties(exporter, hs6, market);
  const landed = useLandedCost(exporter, hs6, market, cost, freight);
  if (!duties.data) return null; // market not covered by the tariff data
  if (landed.isError) {
    return <p className="text-sm text-muted">Couldn’t work out the landed cost right now.</p>;
  }
  const l = landed.data;
  const yours: LandedLine | null | undefined = l?.yours;
  const rival = l?.rivals[0];
  const ToneIcon = TONE_ICON[l?.tone ?? "neutral"];

  return (
    <section
      aria-labelledby={`${id}-title`}
      className="rounded-xl border border-line bg-surface p-4"
    >
      <div className="flex items-center justify-between gap-3">
        <h4 id={`${id}-title`} className="text-sm font-semibold">
          Landed in {marketName}
        </h4>
        <label className="flex items-center gap-1.5 text-xs text-muted">
          Freight
          <input
            inputMode="decimal"
            value={freightText}
            onChange={(e) => setFreightText(e.target.value)}
            placeholder={l?.freight_pct != null ? String(l.freight_pct) : "10"}
            aria-label="Freight and insurance, percent of your price"
            className="h-9 w-14 rounded-lg border border-line bg-surface px-2 text-right text-base text-fg tabular-nums outline-none focus:border-brand/60 focus:ring-4 focus:ring-brand/10 sm:text-sm"
          />
          %
        </label>
      </div>
      {!l || !yours ? (
        <Skeleton className="mt-3 h-24" />
      ) : (
        <>
          <dl className="mt-3 flex flex-col gap-1.5 text-sm" aria-live="polite">
            <Line label="Your price (FOB)" value={perKg(yours.fob_usd_kg)} />
            <Line label="+ Freight and insurance" value={perKg(yours.freight_usd_kg)} />
            <Line
              label={`+ Duty ${rate(yours.duty_pct)}${duties.data.yours.scheme ? ` (${duties.data.yours.scheme})` : ""}`}
              value={perKg(yours.duty_usd_kg)}
            />
            <div className="my-1 border-t border-dashed border-line-strong/60" />
            <Line label="= Landed cost" value={perKg(yours.landed_usd_kg)} strong />
            {l.market_price_usd_kg !== null && (
              <Line
                label={`${marketName} pays${l.price_year ? ` (${l.price_year})` : ""}`}
                value={perKg(l.market_price_usd_kg)}
              />
            )}
            {rival && (
              <Line label={`${rival.country.name} lands at`} value={perKg(rival.landed_usd_kg)} />
            )}
          </dl>
          {l.verdict && l.tone && (
            <div className="mt-3">
              <Callout tone={TONE[l.tone]}>
                <span className="flex gap-2.5">
                  <ToneIcon className="mt-1 h-4 w-4 shrink-0" aria-hidden />
                  {l.verdict}
                </span>
              </Callout>
            </div>
          )}
          {[...l.explanation, ...l.notes].length > 0 && (
            <ul className="mt-3 flex flex-col gap-1 text-xs leading-5 text-subtle">
              {[...l.explanation, ...l.notes].map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
