import {
  BarChart3,
  CircleCheck,
  FlaskConical,
  Lock,
  type LucideIcon,
  Shield,
  Target,
  TrendingDown,
  TrendingUp,
  TriangleAlert,
  Users,
} from "lucide-react";

import { Badge, type Tone, toneClass } from "@/components/ui/badge";
import type { Signal, Verdict } from "@/lib/api/queries";

// Colour supports the words; every badge and chip also carries an icon and a label.
type Action = Verdict["action"];

/** Status colours, always with an icon and words: green to act, amber to check, red to avoid. */
export const VERDICT_TONE: Record<Action, Tone> = {
  go: "positive",
  grow: "positive",
  test: "caution",
  defend: "caution",
  care: "negative",
  hard: "negative",
};

export const VERDICT_ICON: Record<Action, LucideIcon> = {
  go: CircleCheck,
  grow: TrendingUp,
  test: FlaskConical,
  defend: Shield,
  care: TriangleAlert,
  hard: Lock,
};

const SIGNAL_ICON: Record<Exclude<Signal["kind"], "demand">, LucideIcon> = {
  competition: Users,
  position: Target,
  size: BarChart3,
};

function SignalIcon({ signal, className }: { signal: Signal; className: string }) {
  const Icon =
    signal.kind === "demand"
      ? signal.tone === "negative"
        ? TrendingDown
        : TrendingUp
      : SIGNAL_ICON[signal.kind];
  return <Icon className={className} />;
}

export function VerdictBadge({
  verdict,
  large = false,
}: {
  verdict: Pick<Verdict, "action" | "headline" | "tone">;
  large?: boolean;
}) {
  const Icon = VERDICT_ICON[verdict.action];
  return (
    <Badge tone={VERDICT_TONE[verdict.action]} icon={<Icon />} size={large ? "md" : "sm"}>
      {verdict.headline}
    </Badge>
  );
}

/** Compact chips: the signal title, with the figure on hover/focus. */
export function SignalChips({ signals }: { signals: Signal[] }) {
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="Signals">
      {signals.map((s) => (
        <li
          key={s.kind}
          title={s.detail}
          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs ${toneClass[s.tone]}`}
        >
          <SignalIcon signal={s} className="h-3 w-3" />
          {s.title}
        </li>
      ))}
    </ul>
  );
}

/** Full signals: title and the figure behind it, for the market page. */
export function SignalGrid({ signals }: { signals: Signal[] }) {
  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {signals.map((s) => (
        <li
          key={s.kind}
          className="flex items-start gap-3 rounded-xl border border-line bg-surface p-4"
        >
          <span
            className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl ${toneClass[s.tone]}`}
          >
            <SignalIcon signal={s} className="h-4 w-4" />
          </span>
          <span>
            <span className="block text-sm font-medium">{s.title}</span>
            <span className="mt-0.5 block text-sm text-muted">{s.detail}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

/** The verdict with its evidence and the suggested next step. */
export function VerdictPanel({ verdict }: { verdict: Verdict }) {
  return (
    <div>
      <VerdictBadge verdict={verdict} large />
      <p className="mt-3 text-lg leading-8 text-fg">{verdict.summary}</p>
      <p className="mt-3 text-sm text-muted">
        <span className="font-medium text-fg">Next step: </span>
        {verdict.next_step}
      </p>
    </div>
  );
}

/** Plain-words explanation of how verdicts are reached, so users can trust them. */
export function HowWeDecide() {
  return (
    <details className="group rounded-2xl border border-line p-5 text-sm open:bg-surface">
      <summary className="cursor-pointer list-none font-medium text-fg marker:hidden">
        <span className="inline-flex items-center gap-2">
          How we decide
          <span className="text-subtle transition-transform group-open:rotate-90">›</span>
        </span>
      </summary>
      <div className="mt-4 grid gap-4 text-muted md:grid-cols-2">
        <div>
          <p className="font-medium text-fg">Four signals, from customs data</p>
          <ul className="mt-2 flex list-disc flex-col gap-1 pl-4">
            <li>
              <b className="text-fg">Demand</b>: how fast the market’s imports grew over three
              years.
            </li>
            <li>
              <b className="text-fg">Competition</b>: whether the biggest other supplier is losing
              or gaining share, and how much it holds.
            </li>
            <li>
              <b className="text-fg">Your position</b>: how much of the market your country already
              supplies.
            </li>
            <li>
              <b className="text-fg">Size</b>: how much the market imports in a year.
            </li>
          </ul>
        </div>
        <div>
          <p className="font-medium text-fg">Then one verdict, by fixed rules</p>
          <ul className="mt-2 flex list-disc flex-col gap-1 pl-4">
            <li>Already a big supplier: grow your lead, or defend it if a rival is gaining.</li>
            <li>Imports shrinking: approach with care.</li>
            <li>One supplier holds 60% or more and isn’t slipping: hard to break in.</li>
            <li>Demand growing: go for it. Otherwise: worth testing.</li>
          </ul>
          <p className="mt-3 text-xs text-subtle">
            Every figure comes from CEPII BACI customs data. Nothing is estimated.
          </p>
        </div>
      </div>
    </details>
  );
}

export function SellingBadge() {
  return <Badge tone="neutral">You sell here</Badge>;
}
