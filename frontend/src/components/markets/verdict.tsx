import type { ReactNode } from "react";

import type { Signal, Verdict } from "@/lib/api/queries";

type Tone = Signal["tone"];

// Colour supports the words; every badge and chip also carries an icon and a label.
const toneStyles: Record<Tone, string> = {
  positive: "bg-ember/15 text-ember",
  neutral: "bg-ink-line/60 text-sage",
  negative: "bg-caution-bg text-caution",
};

function Icon({ children }: { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 16 16"
      className="h-3.5 w-3.5 shrink-0"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      {children}
    </svg>
  );
}

const verdictIcons: Record<Verdict["action"], ReactNode> = {
  go: <path d="M3 8h9M8.5 4.5 12 8l-3.5 3.5" />,
  test: <path d="M6 2.5h4M7 2.5v4L3.5 13a.7.7 0 0 0 .6 1h7.8a.7.7 0 0 0 .6-1L9 6.5v-4" />,
  grow: <path d="M2.5 11.5 6.5 7.5l2.5 2.5 4.5-5M10 5h3.5v3.5" />,
  defend: <path d="M8 2 3 4v4c0 3 2.2 5 5 6 2.8-1 5-3 5-6V4L8 2Z" />,
  care: <path d="M8 2.5 14 13H2L8 2.5ZM8 7v2.5M8 11.3v.2" />,
  hard: <path d="M3 3l10 10M13 3 3 13" />,
};

const signalIcons: Record<Signal["kind"], (tone: Tone) => ReactNode> = {
  demand: (tone) =>
    tone === "negative" ? (
      <path d="M2.5 4.5 6.5 8.5 9 6l4.5 5M10 11h3.5V7.5" />
    ) : (
      <path d="M2.5 11.5 6.5 7.5l2.5 2.5 4.5-5M10 5h3.5v3.5" />
    ),
  competition: () => (
    <path d="M5.5 7a2 2 0 1 0 0-4 2 2 0 0 0 0 4ZM2 13c0-2 1.6-3.5 3.5-3.5S9 11 9 13M11 7.5a1.7 1.7 0 1 0 0-3.4M12 9.5c1.2.4 2 1.6 2 3" />
  ),
  position: () => (
    <path d="M8 14A6 6 0 1 0 8 2a6 6 0 0 0 0 12ZM8 10.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z" />
  ),
  size: () => <path d="M2.5 13.5h11M4 13.5V8M8 13.5V4.5M12 13.5V10" />,
};

export function VerdictBadge({ verdict, large = false }: { verdict: Verdict; large?: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-medium ${toneStyles[verdict.tone]} ${
        large ? "px-3.5 py-1.5 text-sm" : "px-2.5 py-0.5 text-xs"
      }`}
    >
      <Icon>{verdictIcons[verdict.action]}</Icon>
      {verdict.headline}
    </span>
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
          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] ${toneStyles[s.tone]}`}
        >
          <Icon>{signalIcons[s.kind](s.tone)}</Icon>
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
        <li key={s.kind} className="flex items-start gap-3 rounded-xl border border-ink-line p-4">
          <span
            className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${toneStyles[s.tone]}`}
          >
            <Icon>{signalIcons[s.kind](s.tone)}</Icon>
          </span>
          <span>
            <span className="block text-sm font-medium">{s.title}</span>
            <span className="mt-0.5 block text-sm text-sage">{s.detail}</span>
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
      <p className="mt-3 text-lg leading-8 text-cream">{verdict.summary}</p>
      <p className="mt-3 text-sm text-sage">
        <span className="font-medium text-cream">Next step: </span>
        {verdict.next_step}
      </p>
    </div>
  );
}

/** Plain-words explanation of how verdicts are reached, so users can trust them. */
export function HowWeDecide() {
  return (
    <details className="group rounded-2xl border border-ink-line p-5 text-sm open:bg-ink-raised">
      <summary className="cursor-pointer list-none font-medium text-cream marker:hidden">
        <span className="inline-flex items-center gap-2">
          How we decide
          <span className="text-sage-dim transition-transform group-open:rotate-90">›</span>
        </span>
      </summary>
      <div className="mt-4 grid gap-4 text-sage md:grid-cols-2">
        <div>
          <p className="font-medium text-cream">Four signals, from customs data</p>
          <ul className="mt-2 flex list-disc flex-col gap-1 pl-4">
            <li>
              <b className="text-cream">Demand</b>: how fast the market’s imports grew over three
              years.
            </li>
            <li>
              <b className="text-cream">Competition</b>: whether the biggest other supplier is
              losing or gaining share, and how much it holds.
            </li>
            <li>
              <b className="text-cream">Your position</b>: how much of the market your country
              already supplies.
            </li>
            <li>
              <b className="text-cream">Size</b>: how much the market imports in a year.
            </li>
          </ul>
        </div>
        <div>
          <p className="font-medium text-cream">Then one verdict, by fixed rules</p>
          <ul className="mt-2 flex list-disc flex-col gap-1 pl-4">
            <li>Already a big supplier: grow your lead, or defend it if a rival is gaining.</li>
            <li>Imports shrinking: approach with care.</li>
            <li>One supplier holds 60% or more and isn’t slipping: hard to break in.</li>
            <li>Demand growing: go for it. Otherwise: worth testing.</li>
          </ul>
          <p className="mt-3 text-xs text-sage-dim">
            Every figure comes from CEPII BACI customs data. Nothing is estimated.
          </p>
        </div>
      </div>
    </details>
  );
}

export function SellingBadge() {
  return (
    <span className="rounded-full border border-ink-line px-2.5 py-0.5 text-xs text-sage">
      You sell here
    </span>
  );
}
