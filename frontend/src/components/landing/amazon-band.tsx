import { ArrowRight, Check, ShoppingCart } from "lucide-react";

import { SectionIntro } from "@/components/landing/section";
import { ButtonLink } from "@/components/ui/button";

const POINTS = [
  "Sea freight priced on your order's real size, shared container or full",
  "US duty with the 2026 tariffs: the Section 301 country duties and China's lists",
  "Amazon's 2026 referral, fulfilment and storage fees, with the fuel surcharge",
  "Profit per unit, cash needed for the first order and months to pay it back",
];

/** The free Amazon FBA calculator: a signed-out tool, and the way many sellers find us. */
export function AmazonBand() {
  return (
    <section id="amazon" className="scroll-mt-16 border-t border-line/70">
      <div className="mx-auto grid max-w-6xl grid-cols-1 items-center gap-10 px-4 py-16 sm:px-6 sm:py-24 lg:grid-cols-2 lg:gap-16">
        <div>
          <SectionIntro eyebrow="New · free, no sign-up" title="Thinking of selling on Amazon?">
            Before you order stock, see what one unit really earns on Amazon US, from your
            supplier&apos;s port to the customer&apos;s door.
          </SectionIntro>
          <ButtonLink href="/fba-calculator" size="lg" variant="secondary" className="mt-8">
            Try the FBA calculator <ArrowRight className="h-4 w-4" aria-hidden />
          </ButtonLink>
        </div>
        <ul className="flex flex-col gap-3">
          {POINTS.map((point) => (
            <li
              key={point}
              className="flex items-start gap-3 rounded-2xl border border-line bg-surface p-4 shadow-card"
            >
              <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-soft text-brand">
                <Check className="h-3.5 w-3.5" aria-hidden />
              </span>
              <span className="text-sm leading-6">{point}</span>
            </li>
          ))}
          <li className="flex items-center gap-2 ps-1 text-xs text-subtle">
            <ShoppingCart className="h-3.5 w-3.5" aria-hidden /> Amazon US, standard-size items
          </li>
        </ul>
      </div>
    </section>
  );
}
