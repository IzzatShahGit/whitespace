import {
  ArrowRight,
  ArrowRightLeft,
  CalendarRange,
  Calculator,
  Globe2,
  MapPin,
  Newspaper,
  PackageSearch,
} from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { VerdictBadge } from "@/components/markets/verdict";
import { Callout } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type { ChatCard } from "@/lib/api/queries";
import { capitalize, money, monthLabel, percent, points, signedPercent } from "@/lib/format";
import { localMoney, perKg, usd, weight } from "@/lib/money";

// Cards are built by the server from the data, never written by the model:
// every figure here is exactly what the data says.

type CardOf<T extends ChatCard["type"]> = Extract<ChatCard, { type: T }>;

function Frame({
  icon,
  title,
  subtitle,
  href,
  action = "Open",
  children,
}: {
  icon: ReactNode;
  title: string;
  subtitle?: string;
  href?: string;
  action?: string;
  children: ReactNode;
}) {
  return (
    <Card className="rise-in overflow-hidden">
      <div className="flex items-start justify-between gap-3 px-4 pt-4 sm:px-5">
        <div className="flex min-w-0 items-start gap-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-soft text-brand [&>svg]:h-4 [&>svg]:w-4">
            {icon}
          </span>
          <div className="min-w-0">
            <h3 className="text-sm leading-5 font-semibold">{title}</h3>
            {subtitle && <p className="text-xs text-muted">{subtitle}</p>}
          </div>
        </div>
        {href && (
          <Link
            href={href}
            className="-mr-2 inline-flex min-h-8 shrink-0 items-center gap-1 rounded-lg px-2 text-xs font-medium text-brand transition-colors hover:bg-brand-soft focus-visible:outline-2 focus-visible:outline-brand"
          >
            {action} <ArrowRight aria-hidden className="h-3.5 w-3.5" />
          </Link>
        )}
      </div>
      <div className="px-4 pt-3 pb-4 sm:px-5">{children}</div>
    </Card>
  );
}

/** Label-over-number cells, two to four across. */
function Figures({ items }: { items: { label: string; value: string; note?: string }[] }) {
  return (
    <dl
      className={`grid grid-cols-2 gap-2 ${items.length >= 4 ? "sm:grid-cols-4" : items.length === 3 ? "sm:grid-cols-3" : ""}`}
    >
      {items.map((item) => (
        <div key={item.label} className="flex flex-col rounded-xl bg-surface-2/70 px-3 py-2.5">
          <dt className="text-xs text-muted">{item.label}</dt>
          <dd className="order-first text-base font-semibold tracking-tight tabular-nums">
            {item.value}
          </dd>
          {item.note && <dd className="text-xs text-subtle">{item.note}</dd>}
        </div>
      ))}
    </dl>
  );
}

function MarketsCardView({ card }: { card: CardOf<"markets"> }) {
  return (
    <Frame
      icon={<Globe2 />}
      title={`Best markets for ${card.product.name}`}
      subtitle={`From ${card.exporter.name} · ${card.total} ranked`}
      href={`/app/markets/${card.product.hs6}`}
      action={`All ${card.total}`}
    >
      <ol className="-mx-2 flex flex-col">
        {card.items.map((m) => (
          <li key={m.market.code}>
            <Link
              href={`/app/markets/${card.product.hs6}/${m.market.code}`}
              className="flex items-center gap-3 rounded-xl px-2 py-2.5 transition-colors hover:bg-surface-2 focus-visible:outline-2 focus-visible:outline-brand"
            >
              <span className="w-5 text-center text-sm text-subtle tabular-nums">{m.rank}</span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">
                  {m.market.name}
                  {m.already_selling && (
                    <span className="ml-1.5 text-xs font-normal text-muted">· you sell here</span>
                  )}
                </span>
                <span className="text-xs text-muted tabular-nums">
                  Buys {money(m.imports_usd)} a year ·{" "}
                  <span className={m.growth < 0 ? "text-negative" : "text-positive"}>
                    {signedPercent(m.growth)}/yr
                  </span>
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
      icon={<MapPin />}
      title={`${card.market.name}: ${card.product.name}`}
      subtitle={`Selling from ${card.exporter.name}`}
      href={`/app/markets/${card.product.hs6}/${card.market.code}`}
      action="Full analysis"
    >
      <VerdictBadge verdict={card.verdict} />
      <p className="mt-2 text-sm leading-6 text-fg">{card.verdict.summary}</p>
      <div className="mt-3">
        <Figures
          items={[
            { label: "Imports a year", value: money(card.imports_usd) },
            { label: "Growth a year", value: signedPercent(card.growth) },
            {
              label: `${card.exporter.name}’s share`,
              value: percent(card.exporter_share, { floor: true }),
            },
            {
              label: "Pays per kg",
              value: card.price_usd_kg ? perKg(card.price_usd_kg) : "n/a",
            },
          ]}
        />
      </div>
      <p className="mt-3 text-sm text-muted">
        <span className="font-medium text-fg">Next step: </span>
        {card.verdict.next_step}
      </p>
    </Frame>
  );
}

function SourcingCardView({ card }: { card: CardOf<"sourcing"> }) {
  return (
    <Frame
      icon={<PackageSearch />}
      title={`Where to buy ${card.product.name}`}
      subtitle={`Shipping to ${card.buyer.name}${
        card.median_price_usd_kg ? ` · typical price ${perKg(card.median_price_usd_kg)}` : ""
      }`}
      href={`/app/buy/${card.product.hs6}`}
      action="Compare all"
    >
      <ul className="grid gap-2 sm:grid-cols-2">
        {card.picks.map((p) => (
          <li key={p.kind} className="rounded-xl border border-line p-3">
            <p className="text-xs font-medium text-brand">{p.title}</p>
            <p className="mt-0.5 text-sm font-semibold">{p.country.name}</p>
            <p className="mt-1 text-xs leading-5 text-muted">{p.reason}</p>
          </li>
        ))}
      </ul>
    </Frame>
  );
}

function PriceCardView({ card }: { card: CardOf<"price"> }) {
  const figures = [
    { label: "Your stock", value: localMoney(card.stock_value, card.currency) },
    { label: "In dollars", value: usd(card.value_usd) },
    ...(card.cost_usd_kg !== null ? [{ label: "Your cost", value: perKg(card.cost_usd_kg) }] : []),
    ...(card.market_price_usd_kg !== null
      ? [{ label: `${card.market.name} pays`, value: perKg(card.market_price_usd_kg) }]
      : []),
  ];
  return (
    <Frame
      icon={<Calculator />}
      title={`Price check: ${card.product.name} in ${card.market.name}`}
      href={`/app/markets/${card.product.hs6}/${card.market.code}`}
      action="Open calculator"
    >
      <Figures items={figures} />
      {card.revenue_usd !== null && card.quantity_kg !== null && (
        <p className="mt-3 text-sm text-muted">
          {weight(card.quantity_kg)} at the market’s average price:{" "}
          <span className="font-medium text-fg tabular-nums">{usd(card.revenue_usd)}</span>, before
          freight and duties.
        </p>
      )}
      {card.verdict && card.tone && (
        <div className="mt-3">
          <Callout tone={card.tone}>{card.verdict}</Callout>
        </div>
      )}
    </Frame>
  );
}

function TrendCardView({ card }: { card: CardOf<"trend"> }) {
  const shareChange =
    card.exporter_share_before !== null
      ? points(card.exporter_share_recent - card.exporter_share_before)
      : undefined;
  return (
    <Frame
      icon={<CalendarRange />}
      title={`Latest months: ${card.market.name}`}
      subtitle={`${capitalize(card.product.name)} · ${card.source}`}
      href={`/app/markets/${card.product.hs6}/${card.market.code}`}
      action="See chart"
    >
      <Figures
        items={[
          { label: "Latest month", value: monthLabel(card.latest_month) },
          {
            label: "Last 12 months",
            value: card.change_12m !== null ? signedPercent(card.change_12m) : "n/a",
            note: "vs the year before",
          },
          {
            label: "Your country’s share",
            value: percent(card.exporter_share_recent, { floor: true }),
            note: shareChange,
          },
        ]}
      />
    </Frame>
  );
}

function NewsCardView({ card }: { card: CardOf<"news"> }) {
  return (
    <Frame icon={<Newspaper />} title="Recent news" subtitle={card.query}>
      <ol className="-mx-2 flex flex-col">
        {card.items.map((n, i) => (
          <li key={n.url}>
            <a
              href={n.url}
              target="_blank"
              rel="noreferrer noopener"
              className="flex gap-3 rounded-xl px-2 py-2 transition-colors hover:bg-surface-2 focus-visible:outline-2 focus-visible:outline-brand"
            >
              <span className="mt-0.5 shrink-0 rounded bg-surface-2 px-1 text-xs text-muted tabular-nums">
                N{i + 1}
              </span>
              <span className="min-w-0">
                <span dir="auto" className="line-clamp-2 text-sm text-fg">
                  {n.title}
                </span>
                <span className="text-xs text-subtle">
                  {n.domain}
                  {n.published && ` · ${n.published}`}
                </span>
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
    <Frame icon={<ArrowRightLeft />} title="Currency" subtitle="At today’s rate">
      <p className="flex flex-wrap items-baseline gap-x-2 text-lg font-semibold tabular-nums">
        {localMoney(card.amount, card.from_currency)}
        <span className="text-subtle">=</span>
        {localMoney(card.result, card.to_currency)}
      </p>
    </Frame>
  );
}

/** One data card. Types this version doesn't know yet render nothing, never an error. */
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
    default:
      return null;
  }
}
