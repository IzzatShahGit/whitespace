"use client";

import { ArrowLeft, Plus, Printer, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { type ReactNode, use } from "react";

import { VerdictBadge } from "@/components/markets/verdict";
import { Button } from "@/components/ui/button";
import { Card, Page, PageHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/empty";
import { useDuties } from "@/lib/api/landed-cost";
import { useMarketDetail, useMarkets } from "@/lib/api/queries";
import { capitalize, money, percent, points, signedPercent } from "@/lib/format";
import { perKg } from "@/lib/money";
import { useExporter } from "@/lib/use-exporter";

const MAX = 3;

function Row({ label, cells }: { label: string; cells: ReactNode[] }) {
  return (
    <tr className="border-t border-line">
      <th scope="row" className="py-3 pr-4 text-left text-xs font-medium text-muted">
        {label}
      </th>
      {cells.map((cell, i) => (
        <td key={i} className="py-3 pr-4 text-sm tabular-nums">
          {cell}
        </td>
      ))}
    </tr>
  );
}

/** One market's column: its figures in the same rows as the others. */
function useColumn(exporter: string | undefined, hs6: string, market: string) {
  const who = market ? exporter : undefined; // an empty slot fetches nothing
  const detail = useMarketDetail(who, hs6, market);
  const duties = useDuties(who, hs6, market);
  return { detail, duties };
}

function Columns({
  exporter,
  hs6,
  markets,
  onRemove,
}: {
  exporter: string;
  hs6: string;
  markets: string[];
  onRemove: (code: string) => void;
}) {
  // Fixed number of hook calls (MAX), whatever is selected.
  const columns = [
    useColumn(exporter, hs6, markets[0] ?? ""),
    useColumn(exporter, hs6, markets[1] ?? ""),
    useColumn(exporter, hs6, markets[2] ?? ""),
  ].slice(0, markets.length);

  if (columns.some((c) => c.detail.isPending)) return <Skeleton className="h-96" />;
  const items = columns.map((c) => c.detail.data?.market);
  const cell = (fn: (i: number) => ReactNode) => items.map((_, i) => fn(i));

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[36rem]">
        <thead>
          <tr>
            <th className="w-40" />
            {items.map((m, i) => (
              <th key={markets[i]} className="pr-4 pb-3 text-left align-bottom">
                <span className="flex items-center gap-2">
                  <Link
                    href={`/app/markets/${hs6}/${markets[i]}`}
                    className="text-lg font-semibold hover:text-brand"
                  >
                    {m?.market.name ?? markets[i]}
                  </Link>
                  <button
                    type="button"
                    aria-label={`Remove ${m?.market.name ?? markets[i]}`}
                    onClick={() => onRemove(markets[i])}
                    className="no-print rounded p-1 text-subtle hover:text-negative"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <Row
            label="Verdict"
            cells={cell((i) => items[i] && <VerdictBadge verdict={items[i].verdict} />)}
          />
          <Row label="Rank" cells={cell((i) => items[i] && `#${items[i].rank}`)} />
          <Row
            label="Market size"
            cells={cell((i) => items[i] && money(items[i].market_imports_usd))}
          />
          <Row
            label="Growth a year"
            cells={cell((i) => items[i] && signedPercent(items[i].import_growth_3y))}
          />
          <Row
            label="Your share"
            cells={cell((i) => items[i] && percent(items[i].exporter_share, { floor: true }))}
          />
          <Row
            label="Main rival"
            cells={cell((i) => {
              const m = items[i];
              if (!m?.top_rival) return "None";
              const change =
                m.top_rival_share_change !== null ? ` (${points(m.top_rival_share_change)})` : "";
              return `${m.top_rival.name}${change}`;
            })}
          />
          <Row
            label="Pays per kg"
            cells={cell((i) =>
              items[i]?.market_unit_price_usd_kg ? perKg(items[i].market_unit_price_usd_kg) : "n/a",
            )}
          />
          <Row
            label="Your import duty"
            cells={cell((i) => {
              const d = columns[i].duties.data;
              if (columns[i].duties.isPending) return "…";
              if (!d) return "n/a";
              return `${d.yours.rate_pct}%${d.yours.scheme ? ` (${d.yours.scheme})` : ""}`;
            })}
          />
          <Row label="Next step" cells={cell((i) => items[i]?.verdict.next_step)} />
        </tbody>
      </table>
    </div>
  );
}

/** Up to three markets for one product, side by side; printable as a report. */
export function CompareView({ params }: { params: Promise<{ hs6: string }> }) {
  const { hs6 } = use(params);
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();
  const exporter = useExporter();
  const selected = (search.get("m") ?? "")
    .split(",")
    .map((c) => c.trim().toUpperCase())
    .filter((c) => /^[A-Z]{3}$/.test(c))
    .slice(0, MAX);
  const ranked = useMarkets(exporter.code, hs6);
  const options = (ranked.data?.pages[0]?.items ?? []).filter(
    (m) => !selected.includes(m.market.code),
  );
  const product = ranked.data?.pages[0]?.product;
  const exporterName = ranked.data?.pages[0]?.exporter.name;

  function setMarkets(codes: string[]) {
    const next = new URLSearchParams(search);
    next.set("m", codes.join(","));
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  }

  return (
    <Page>
      <PageHeader
        eyebrow={
          <Link
            href={`/app/markets/${hs6}`}
            className="no-print inline-flex items-center gap-1 hover:text-fg"
          >
            <ArrowLeft className="h-4 w-4" /> All markets
          </Link>
        }
        title={`Compare markets${product ? ` for ${product.name}` : ""}`}
        description={
          exporterName
            ? `Side by side, for exporters in ${exporterName}. Up to ${MAX} markets.`
            : undefined
        }
        actions={
          <Button variant="secondary" className="no-print" onClick={() => window.print()}>
            <Printer /> Print or save PDF
          </Button>
        }
      />

      {selected.length < MAX && (
        <div className="no-print flex flex-wrap items-center gap-2">
          <span className="text-sm text-muted">Add a market:</span>
          {options.slice(0, 8).map((m) => (
            <button
              key={m.market.code}
              type="button"
              onClick={() => setMarkets([...selected, m.market.code])}
              className="inline-flex items-center gap-1 rounded-full border border-line px-3 py-1 text-sm text-muted transition-colors hover:border-brand/40 hover:text-fg"
            >
              <Plus className="h-3.5 w-3.5" /> {m.market.name}
            </button>
          ))}
        </div>
      )}

      <Card className="p-5 sm:p-6">
        {!exporter.code ? (
          <Skeleton className="h-64" />
        ) : selected.length === 0 ? (
          <p className="text-sm text-muted">Pick up to {MAX} markets above to compare them.</p>
        ) : (
          <Columns
            exporter={exporter.code}
            hs6={hs6}
            markets={selected}
            onRemove={(code) => setMarkets(selected.filter((c) => c !== code))}
          />
        )}
      </Card>
      {product && (
        <p className="text-xs text-subtle">
          {capitalize(product.name)} (HS {product.hs6}). Customs data (CEPII BACI); duties from WITS
          / UK Trade Tariff. Figures are averages, not quotes.
        </p>
      )}
    </Page>
  );
}
