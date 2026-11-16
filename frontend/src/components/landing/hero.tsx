import { BadgeCheck, Languages, Wallet } from "lucide-react";
import type { CSSProperties } from "react";

import { IsoGrid } from "@/components/brand/iso-grid";
import { TryDemo } from "@/components/landing/try-demo";
import { ButtonLink } from "@/components/ui/button";

const delay = (ms: number) => ({ "--delay": `${ms}ms` }) as CSSProperties;

const PROOF = [
  { icon: BadgeCheck, text: "8 years of customs data, every country" },
  { icon: Languages, text: "Answers in Urdu, Bangla, Turkish, Arabic…" },
  { icon: Wallet, text: "Prices in lakh, crore and your own currency" },
];

export function Hero() {
  return (
    <section className="relative overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute -top-40 right-[-10rem] h-[36rem] w-[36rem] rounded-full bg-brand-soft blur-3xl"
      />
      <div className="relative mx-auto grid max-w-6xl gap-10 px-4 pt-10 pb-16 sm:px-6 sm:pt-16 lg:grid-cols-[1fr_minmax(0,34rem)] lg:gap-14 lg:pt-20 lg:pb-24">
        <div className="flex flex-col gap-6 lg:pt-6">
          <IsoGrid animated className="w-24 sm:w-28" title="Whitespace: one gap, one opportunity" />
          <p
            className="rise-in w-fit rounded-full border border-line bg-surface px-3 py-1 text-xs font-medium text-muted"
            style={delay(0)}
          >
            For exporters in Pakistan, Bangladesh, Vietnam, India and 6 more countries
          </p>
          <h1
            className="rise-in text-[2.5rem] leading-[1.05] font-semibold tracking-tight text-balance sm:text-5xl xl:text-[3.5rem]"
            style={delay(60)}
          >
            Find the countries buying what you make.
          </h1>
          <p
            className="rise-in max-w-xl text-lg leading-8 text-pretty text-muted"
            style={delay(120)}
          >
            Whitespace reads every country’s customs records and tells you, in plain words, where to
            sell your product next, where to buy for less, and what your stock is worth abroad.
          </p>
          <ul className="rise-in flex flex-col gap-2.5" style={delay(180)}>
            {PROOF.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-center gap-2.5 text-[15px] text-fg">
                <Icon aria-hidden className="h-5 w-5 shrink-0 text-brand" strokeWidth={1.75} />
                {text}
              </li>
            ))}
          </ul>
          <div className="rise-in flex flex-wrap items-center gap-3" style={delay(240)}>
            <ButtonLink href="/signup" size="lg">
              Start free
            </ButtonLink>
            <p className="text-sm text-muted">No card needed. Free to start.</p>
          </div>
        </div>

        <div id="try" className="relative scroll-mt-24">
          <div className="rounded-3xl border border-line bg-surface p-5 shadow-pop sm:p-6">
            <div className="mb-5 flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-medium tracking-wide text-brand uppercase">
                  Try it now · no sign-up
                </p>
                <h2 className="mt-1 text-xl font-semibold tracking-tight">
                  Where could you sell next?
                </h2>
              </div>
              <span className="flex shrink-0 items-center gap-1.5 rounded-full bg-positive-soft px-2.5 py-1 text-xs font-medium text-positive">
                <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-positive" />
                Live data
              </span>
            </div>
            <TryDemo />
          </div>
        </div>
      </div>
    </section>
  );
}
