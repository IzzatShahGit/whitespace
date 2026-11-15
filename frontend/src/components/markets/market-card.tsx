import Link from "next/link";

import { SellingBadge, SignalChips, VerdictBadge } from "@/components/markets/verdict";
import type { MarketItem } from "@/lib/api/queries";
import { money, percent, signedPercent } from "@/lib/format";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-sage-dim">{label}</dt>
      <dd className="mt-0.5 text-sm font-medium tabular-nums">{value}</dd>
    </div>
  );
}

/**
 * One ranked market: the verdict first (what to do), then the signals (why), then
 * the key figures. `compact` (dashboard) leaves out the written summary.
 */
export function MarketCard({
  item,
  href,
  compact = false,
}: {
  item: MarketItem;
  href: string;
  compact?: boolean;
}) {
  return (
    <Link
      href={href}
      className="group flex h-full flex-col rounded-2xl border border-ink-line bg-ink-raised p-5 transition-all duration-200 hover:-translate-y-0.5 hover:border-sage-dim/60 focus-visible:outline-2 focus-visible:outline-ember"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <span className="font-mono text-sm text-sage-dim">#{item.rank}</span>
          <h3 className="text-lg font-medium">{item.market.name}</h3>
        </div>
        {item.already_selling && <SellingBadge />}
      </div>

      <div className="mt-3">
        <VerdictBadge verdict={item.verdict} />
      </div>
      {!compact && <p className="mt-3 text-sm leading-6 text-sage">{item.verdict.summary}</p>}

      <div className="mt-4">
        <SignalChips signals={item.signals} />
      </div>

      <dl className="mt-4 grid grid-cols-3 gap-3 border-t border-ink-line/60 pt-4">
        <Stat label="Imports" value={money(item.market_imports_usd)} />
        <Stat label="Growth / yr" value={signedPercent(item.import_growth_3y)} />
        <Stat label="Your share" value={percent(item.exporter_share, { floor: true })} />
      </dl>

      <span className="mt-auto pt-4 text-sm text-sage-dim transition-colors group-hover:text-cream">
        See the market →
      </span>
    </Link>
  );
}
