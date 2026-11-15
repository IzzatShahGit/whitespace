import type { CSSProperties } from "react";

import { IsoGrid } from "@/components/brand/iso-grid";
import { ButtonLink } from "@/components/ui/button";

const delay = (ms: number) => ({ "--delay": `${ms}ms` }) as CSSProperties;

export function Hero() {
  return (
    <section className="relative overflow-hidden">
      {/* soft ember glow behind the grid */}
      <div className="pointer-events-none absolute top-10 -right-40 h-[520px] w-[520px] rounded-full bg-ember/10 blur-[120px]" />

      <div className="mx-auto grid max-w-6xl items-center gap-12 px-6 pt-16 pb-24 md:grid-cols-[1.1fr_1fr] md:pt-24">
        <div className="flex flex-col gap-7">
          <p
            className="rise-in w-fit rounded-full border border-ink-line px-3 py-1 text-xs text-sage"
            style={delay(0)}
          >
            Free global trade data · AI market briefs
          </p>
          <h1
            className="rise-in text-4xl leading-[1.08] font-semibold tracking-tight sm:text-6xl"
            style={delay(120)}
          >
            Find the market <br className="hidden sm:block" />
            <span className="text-sage">where your product</span>{" "}
            <span className="text-ember">fits next.</span>
          </h1>
          <p className="rise-in max-w-lg text-lg leading-8 text-sage" style={delay(240)}>
            Type your product in plain words. Whitespace ranks the countries where demand is
            growing, competitors are losing ground, and your country already competes well.
          </p>
          <div className="rise-in flex flex-wrap gap-3" style={delay(360)}>
            <ButtonLink href="/signup">Find my markets</ButtonLink>
            <ButtonLink href="#how-it-works" variant="secondary">
              See how it works
            </ButtonLink>
          </div>
        </div>

        <div className="relative mx-auto w-full max-w-md">
          <IsoGrid animated className="w-full drop-shadow-[0_30px_40px_rgba(0,0,0,0.45)]" />
        </div>
      </div>
    </section>
  );
}
