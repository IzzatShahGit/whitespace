import {
  Bell,
  CalendarClock,
  FileText,
  type LucideIcon,
  PackageSearch,
  ShieldCheck,
  Sparkles,
  Tag,
  TrendingUp,
  Truck,
  Wallet,
} from "lucide-react";
import type { ReactNode } from "react";

import { ExampleTag, SectionIntro } from "@/components/landing/section";
import { VerdictBadge } from "@/components/markets/verdict";
import { Badge } from "@/components/ui/badge";

function Tile({
  icon: Icon,
  title,
  body,
  className = "",
  children,
}: {
  icon: LucideIcon;
  title: string;
  body: string;
  className?: string;
  children?: ReactNode;
}) {
  return (
    <article
      className={`flex flex-col gap-5 rounded-2xl border border-line bg-surface p-5 shadow-card sm:p-6 ${className}`}
    >
      <div>
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-soft text-brand">
          <Icon aria-hidden className="h-5 w-5" strokeWidth={1.75} />
        </span>
        <h3 className="mt-4 text-lg font-semibold tracking-tight">{title}</h3>
        <p className="mt-1.5 text-[15px] leading-7 text-muted">{body}</p>
      </div>
      {children && <div className="mt-auto">{children}</div>}
    </article>
  );
}

// Figures in the examples are real (towels from Pakistan, customs data 2024), but frozen.
const SELL = [
  { name: "Kyrgyzstan", size: "$40M", growth: "+21%", action: "go", headline: "Go for it" },
  { name: "Japan", size: "$535M", growth: "+2%", action: "go", headline: "Go for it" },
  { name: "Thailand", size: "$164M", growth: "+19%", action: "hard", headline: "Hard to break in" },
] as const;

function SellExample() {
  return (
    <div className="rounded-xl border border-line bg-canvas/60 p-2">
      <div className="flex items-center justify-between px-2 pt-1 pb-2 text-xs text-subtle">
        <span>Towels from Pakistan · 60 markets ranked</span>
        <ExampleTag />
      </div>
      <ol className="flex flex-col gap-1">
        {SELL.map((m, i) => (
          <li
            key={m.name}
            className="flex items-center gap-3 rounded-lg bg-surface px-3 py-2.5 shadow-card"
          >
            <span className="w-4 text-sm text-subtle tabular-nums">{i + 1}</span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">{m.name}</span>
              <span className="text-xs text-muted tabular-nums">
                {m.size} a year · {m.growth}/yr
              </span>
            </span>
            <VerdictBadge verdict={{ action: m.action, headline: m.headline, tone: "neutral" }} />
          </li>
        ))}
      </ol>
    </div>
  );
}

const PICKS = [
  { icon: Tag, title: "Cheapest", body: "Lowest price per kg" },
  { icon: Truck, title: "Most reliable", body: "Has supplied every year" },
  { icon: TrendingUp, title: "Rising", body: "Winning share fast" },
];

function BuyExample() {
  return (
    <ul className="flex flex-col gap-1.5">
      {PICKS.map(({ icon: Icon, title, body }) => (
        <li
          key={title}
          className="flex items-center gap-3 rounded-lg border border-line px-3 py-2 text-sm"
        >
          <Icon aria-hidden className="h-4 w-4 text-brand" />
          <span className="font-medium">{title}</span>
          <span className="ml-auto text-xs text-muted">{body}</span>
        </li>
      ))}
    </ul>
  );
}

function AskExample() {
  return (
    <div className="flex flex-col gap-2.5 text-sm">
      <p
        dir="auto"
        className="ml-6 rounded-2xl rounded-br-md bg-brand-soft px-3.5 py-2.5 leading-6 text-fg"
      >
        Mere paas 18 lakh ke towels hain, 5 ton. Germany mein bech sakta hoon?
      </p>
      <div className="mr-4 rounded-2xl rounded-bl-md border border-line px-3.5 py-2.5 leading-6">
        <p dir="auto">
          Haan. Germany average <b className="font-semibold">$7.49/kg</b> deta hai, aur aapki laagat{" "}
          <b className="font-semibold">$1.30/kg</b> hai.
        </p>
        <p className="mt-2">
          <Badge tone="positive" icon={<ShieldCheck />}>
            Every figure checked against the data
          </Badge>
        </p>
      </div>
    </div>
  );
}

function MoneyExample() {
  return (
    <div className="rounded-xl border border-line bg-canvas/60 p-4">
      <div className="flex items-center justify-between text-xs text-subtle">
        <span>Your stock</span>
        <ExampleTag />
      </div>
      <p className="mt-1 text-lg font-semibold tabular-nums">PKR 18,00,000</p>
      <p className="text-sm text-muted">18 lakh · about $6,500</p>
      <div className="mt-3 grid grid-cols-2 gap-2 border-t border-line pt-3 text-sm">
        <p>
          <span className="block text-xs text-subtle">Your cost</span>
          <span className="font-medium tabular-nums">$1.30/kg</span>
        </p>
        <p>
          <span className="block text-xs text-subtle">Germany pays</span>
          <span className="font-medium tabular-nums">$7.49/kg</span>
        </p>
      </div>
    </div>
  );
}

function AlertExample() {
  return (
    <ul className="flex flex-col gap-1.5">
      {[
        { title: "New monthly figures: Germany", body: "Towel imports, to September" },
        { title: "Kyrgyzstan moved up", body: "Now your #1 market for towels" },
      ].map((n) => (
        <li key={n.title} className="flex items-start gap-3 rounded-lg border border-line p-3">
          <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-accent" aria-hidden />
          <span className="text-sm">
            <span className="block font-medium">{n.title}</span>
            <span className="text-xs text-muted">{n.body}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

export function Features() {
  return (
    <section id="inside" className="scroll-mt-16 border-t border-line/70">
      <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-24">
        <SectionIntro eyebrow="What’s inside" title="Everything a small exporter needs to decide.">
          Selling, buying, pricing and keeping watch, in one place and in plain words.
        </SectionIntro>
        <div className="mt-10 grid gap-4 sm:mt-14 md:grid-cols-2 lg:grid-cols-3">
          <Tile
            icon={TrendingUp}
            title="Where to sell"
            body="Every importing country ranked for your product, with a verdict, the reasons behind it, and the next step to take."
            className="md:col-span-2"
          >
            <SellExample />
          </Tile>
          <Tile
            icon={PackageSearch}
            title="Where to buy"
            body="Need yarn, dyes or machines? Compare supplier countries on price per kg, track record and momentum."
          >
            <BuyExample />
          </Tile>
          <Tile
            icon={Sparkles}
            title="An AI guide that speaks your language"
            body="Ask in Urdu, Roman Urdu, Bangla, Turkish or English. It answers from the data, and checks every figure before you see it."
          >
            <AskExample />
          </Tile>
          <Tile
            icon={Wallet}
            title="Your money, your units"
            body="Type “18 lakh rupees” and see it in dollars, then against what each market pays per kg."
          >
            <MoneyExample />
          </Tile>
          <Tile
            icon={Bell}
            title="Alerts on markets you watch"
            body="Add a market to your watchlist and we tell you when new figures land or its verdict changes."
          >
            <AlertExample />
          </Tile>
          <Tile
            icon={FileText}
            title="Market briefs with this month’s news"
            body="One click writes a brief on any market: why the gap exists, what to check, and recent news with links."
            className="md:col-span-2 lg:col-span-3"
          >
            <div className="flex flex-wrap gap-2">
              <Badge tone="brand" icon={<CalendarClock />}>
                Monthly EU and US figures
              </Badge>
              <Badge tone="brand" icon={<FileText />}>
                Sources linked
              </Badge>
              <Badge tone="brand" icon={<ShieldCheck />}>
                Figures checked against the data
              </Badge>
            </div>
          </Tile>
        </div>
      </div>
    </section>
  );
}
