import Link from "next/link";
import type { ReactNode } from "react";

import { VerdictBadge } from "@/components/markets/verdict";
import type { ChatCard } from "@/lib/api/queries";
import { capitalize, money, percent, signedPercent } from "@/lib/format";
import { localMoney, perKg, usd, weight } from "@/lib/money";

// Cards are built by the server from the data, never written by the model:
// every figure here is exactly what the data says.

type CardOf<T extends ChatCard["type"]> = Extract<ChatCard, { type: T }>;

const toneStyles = {
  positive: "bg-ember/15 text-ember",
  neutral: "bg-ink-line/60 text-sage",
  negative: "bg-caution-bg text-caution",
} as const;

function Frame({
  title,
  href,
  action,
  children,
}: {
  title: string;
  href?: string;
  action?: string;
  children: ReactNode;
}) {
  return (
    <section className="rise-in rounded-2xl border border-ink-line bg-ink-raised p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-sm font-medium">{title}</h3>
        {href && (
          <Link href={href} className="shrink-0 text-xs text-sage hover:text-cream">
            {action ?? "Open"} →
          </Link>
        )}
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[11px] text-sage-dim">{label}</p>
      <p className="text-sm text-cream tabular-nums">{value}</p>
    </div>
  );
}

function MarketsCardView({ card }: { card: CardOf<"markets"> }) {
  return (
    <Frame
      title={`Best markets for ${card.product.name} from ${card.exporter.name}`}
      href={`/app/markets/${card.product.hs6}`}
      action={`All ${card.total}`}
    >
      <ol className="flex flex-col">
        {card.items.map((m) => (
          <li key={m.market.code}>
            <Link
              href={`/app/markets/${card.product.hs6}/${m.market.code}`}
              className="grid grid-cols-[1.5rem_1fr_auto] items-center gap-3 rounded-lg px-2 py-2 hover:bg-ink-line/40"
            >
              <span className="text-xs text-sage-dim tabular-nums">{m.rank}</span>
              <span className="min-w-0">
                <span className="block truncate text-sm">
                  {m.market.name}
                  {m.already_selling && <span className="ml-2 text-xs text-sage">· you sell</span>}
                </span>
                <span className="text-xs text-sage-dim tabular-nums">
                  {money(m.imports_usd)} · {signedPercent(m.growth)}/yr
                </span>
              </span>
              <VerdictBadge verdict={m} />
            </Link>
          </li>
        ))}
      </ol>
    </Frame>
  );
}

function MarketCardView({ card }: { card: CardOf<"market"> }) {
  return (
    <Frame
      title={`${card.market.name} · ${capitalize(card.product.name)}`}
      href={`/app/markets/${card.product.hs6}/${card.market.code}`}
      action="Full analysis"
    >
      <div className="flex flex-wrap items-center gap-2">
        <VerdictBadge verdict={card.verdict} />
      </div>
      <p className="mt-2 text-sm leading-6 text-sage">{card.verdict.summary}</p>
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Market size" value={money(card.imports_usd)} />
        <Stat label="Growth / yr" value={signedPercent(card.growth)} />
        <Stat
          label={`${card.exporter.name}'s share`}
          value={percent(card.exporter_share, { floor: true })}
        />
        <Stat label="Pays per kg" value={card.price_usd_kg ? perKg(card.price_usd_kg) : "n/a"} />
      </div>
    </Frame>
  );
}

function SourcingCardView({ card }: { card: CardOf<"sourcing"> }) {
  return (
    <Frame
      title={`Where to buy ${card.product.name}`}
      href={`/app/buy/${card.product.hs6}`}
      action="Compare all"
    >
      <ul className="grid gap-2 sm:grid-cols-2">
        {card.picks.map((p) => (
          <li key={p.kind} className="rounded-xl border border-ink-line p-3">
            <p className="text-[11px] text-ember">{p.title}</p>
            <p className="text-sm font-medium">{p.country.name}</p>
            <p className="mt-1 text-xs leading-5 text-sage">{p.reason}</p>
          </li>
        ))}
      </ul>
      {card.median_price_usd_kg && (
        <p className="mt-2 text-xs text-sage-dim">Median price {perKg(card.median_price_usd_kg)}</p>
      )}
    </Frame>
  );
}

function PriceCardView({ card }: { card: CardOf<"price"> }) {
  return (
    <Frame
      title={`Your price check · ${card.market.name}`}
      href={`/app/markets/${card.product.hs6}/${card.market.code}`}
      action="Open calculator"
    >
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Your stock" value={localMoney(card.stock_value, card.currency)} />
        <Stat label="In dollars" value={usd(card.value_usd)} />
        {card.cost_usd_kg !== null && <Stat label="Your cost" value={perKg(card.cost_usd_kg)} />}
        {card.market_price_usd_kg !== null && (
          <Stat label={`${card.market.name} pays`} value={perKg(card.market_price_usd_kg)} />
        )}
      </div>
      {card.revenue_usd !== null && card.quantity_kg !== null && (
        <p className="mt-3 text-xs text-sage">
          {weight(card.quantity_kg)} at the market’s average price: {usd(card.revenue_usd)}, before
          freight and duties.
        </p>
      )}
      {card.verdict && card.tone && (
        <p className={`mt-3 rounded-xl px-3 py-2 text-sm ${toneStyles[card.tone]}`}>
          {card.verdict}
        </p>
      )}
    </Frame>
  );
}

function TrendCardView({ card }: { card: CardOf<"trend"> }) {
  return (
    <Frame
      title={`Latest months · ${card.market.name}`}
      href={`/app/markets/${card.product.hs6}/${card.market.code}`}
      action="See chart"
    >
      <div className="grid grid-cols-3 gap-3">
        <Stat label="Latest month" value={card.latest_month} />
        <Stat
          label="Last 12 months"
          value={card.change_12m !== null ? signedPercent(card.change_12m) : "n/a"}
        />
        <Stat
          label="Your country's share"
          value={percent(card.exporter_share_recent, { floor: true })}
        />
      </div>
      <p className="mt-2 text-xs text-sage-dim">{card.source}</p>
    </Frame>
  );
}

function NewsCardView({ card }: { card: CardOf<"news"> }) {
  return (
    <Frame title="Recent news">
      <ol className="flex flex-col gap-2">
        {card.items.map((n, i) => (
          <li key={n.url} className="flex gap-2 text-sm">
            <span className="mt-0.5 text-[10px] text-sage-dim">N{i + 1}</span>
            <a
              href={n.url}
              target="_blank"
              rel="noreferrer noopener"
              className="min-w-0 hover:text-cream"
            >
              <span className="line-clamp-2 text-cream/90">{n.title}</span>
              <span className="text-xs text-sage-dim">
                {n.domain}
                {n.published && ` · ${n.published}`}
              </span>
            </a>
          </li>
        ))}
      </ol>
    </Frame>
  );
}

function MoneyCardView({ card }: { card: CardOf<"money"> }) {
  return (
    <Frame title="Currency">
      <p className="text-lg font-semibold tabular-nums">
        {localMoney(card.amount, card.from_currency)} <span className="text-sage-dim">=</span>{" "}
        {localMoney(card.result, card.to_currency)}
      </p>
    </Frame>
  );
}

export function ChatCardView({ card }: { card: ChatCard }) {
  switch (card.type) {
    case "markets":
      return <MarketsCardView card={card} />;
    case "market":
      return <MarketCardView card={card} />;
    case "sourcing":
      return <SourcingCardView card={card} />;
    case "price":
      return <PriceCardView card={card} />;
    case "trend":
      return <TrendCardView card={card} />;
    case "news":
      return <NewsCardView card={card} />;
    case "money":
      return <MoneyCardView card={card} />;
  }
}
