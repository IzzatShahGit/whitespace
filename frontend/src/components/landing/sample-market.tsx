import type { CSSProperties } from "react";

// An illustrative result card. The numbers are made up, and labelled as such.
const markets = [
  { country: "Germany", label: "Strong", score: 0.86 },
  { country: "Poland", label: "Strong", score: 0.79 },
  { country: "Saudi Arabia", label: "Good", score: 0.68 },
  { country: "Canada", label: "Watch", score: 0.52 },
];

const reasons = [
  "Imports grew 15% a year since 2021",
  "China's share fell from 40% to 31%",
  "Pakistan holds 3%: plenty of room",
];

const delay = (ms: number) => ({ "--delay": `${ms}ms` }) as CSSProperties;

export function SampleMarket() {
  return (
    <section className="border-t border-ink-line/60">
      <div className="mx-auto grid max-w-6xl items-center gap-12 px-6 py-24 md:grid-cols-2">
        <div>
          <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            Recommendations, <span className="text-sage">not raw tables.</span>
          </h2>
          <p className="mt-4 max-w-md leading-8 text-sage">
            Each market comes with a clear label and three plain reasons, so you know why it made
            the list, and a note on how fresh the data is.
          </p>
        </div>

        <div className="rounded-2xl border border-ink-line bg-ink-raised p-6 shadow-[0_30px_60px_-30px_rgba(0,0,0,0.6)]">
          <div className="flex items-baseline justify-between">
            <p className="text-sm text-sage">Cotton terry towels · from Pakistan</p>
            <p className="text-xs text-sage-dim">Example data</p>
          </div>
          <ul className="mt-5 flex flex-col gap-4">
            {markets.map((m, i) => (
              <li key={m.country} className="flex items-center gap-4">
                <span className="w-28 shrink-0 text-sm">{m.country}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-ink">
                  <div
                    className={`grow-x h-full rounded-full ${i === 0 ? "bg-ember" : "bg-tile-2"}`}
                    style={{ width: `${m.score * 100}%`, ...delay(200 + i * 150) }}
                  />
                </div>
                <span
                  className={`w-14 text-right text-xs ${i === 0 ? "text-ember" : "text-sage"}`}
                >
                  {m.label}
                </span>
              </li>
            ))}
          </ul>
          <div className="mt-6 border-t border-ink-line pt-5">
            <p className="text-sm font-medium">Why Germany</p>
            <ul className="mt-3 flex flex-col gap-2">
              {reasons.map((r) => (
                <li key={r} className="flex items-start gap-2 text-sm text-sage">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rotate-45 bg-ember" />
                  {r}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
