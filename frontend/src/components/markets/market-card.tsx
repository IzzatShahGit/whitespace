import Link from "next/link";

import { LabelPill, SellingBadge } from "@/components/markets/label-pill";
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

/** One ranked market. `compact` shows a single reason (dashboard); full shows all three. */
export function MarketCard({
  item,
  href,
  compact = false,
}: {
  item: MarketItem;
  href: string;
  compact?: boolean;
}) {
  const reasons = compact ? item.reasons.slice(0, 1) : item.reasons;
  return (
    <Link
      href={href}
      className="group block rounded-2xl border border-ink-line bg-ink-raised p-5 transition-all duration-200 hover:-translate-y-0.5 hover:border-sage-dim/60 focus-visible:outline-2 focus-visible:outline-ember"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <span className="font-mono text-sm text-sage-dim">#{item.rank}</span>
          <h3 className="text-lg font-medium">{item.market.name}</h3>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {item.already_selling && <SellingBadge />}
          <LabelPill label={item.label} />
        </div>
      </div>

      <dl className="mt-4 grid grid-cols-3 gap-3">
        <Stat label="Imports" value={money(item.market_imports_usd)} />
        <Stat label="Growth / yr" value={signedPercent(item.import_growth_3y)} />
        <Stat label="Your share" value={percent(item.exporter_share, { floor: true })} />
      </dl>

      <ul className="mt-4 flex flex-col gap-1.5">
        {reasons.map((reason) => (
          <li key={reason} className="flex items-start gap-2 text-sm text-sage">
            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rotate-45 bg-ember" aria-hidden />
            {reason}
          </li>
        ))}
      </ul>
      <span className="mt-4 inline-block text-sm text-sage-dim transition-colors group-hover:text-cream">
        See the market →
      </span>
    </Link>
  );
}
