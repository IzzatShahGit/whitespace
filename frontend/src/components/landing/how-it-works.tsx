import { Compass, MessageCircleQuestion, PenLine } from "lucide-react";

import { SectionIntro } from "@/components/landing/section";

const STEPS = [
  {
    icon: PenLine,
    title: "Say what you make",
    body: "Type “towels” or “basmati rice”, not a customs code. We match your words to the right product, and you tell us your country once.",
  },
  {
    icon: Compass,
    title: "See where it sells",
    body: "Every country that imports it, ranked: is demand growing, are rivals losing ground, is there room for you? Each gets a plain verdict, like “Go for it”.",
  },
  {
    icon: MessageCircleQuestion,
    title: "Decide with the facts",
    body: "Open a market for prices, rivals and the latest monthly figures, check your price in rupees or taka, or ask the guide in your own language.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="scroll-mt-16 border-t border-line/70 bg-surface">
      <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-24">
        <SectionIntro
          eyebrow="How it works"
          title="From a product name to a shortlist of countries, in a minute."
        />
        <ol className="mt-10 grid gap-8 sm:mt-14 md:grid-cols-3 md:gap-6">
          {STEPS.map(({ icon: Icon, title, body }, i) => (
            <li key={title} className="relative flex gap-4 md:flex-col">
              <div className="flex shrink-0 items-center gap-3 md:w-full">
                <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-soft text-brand">
                  <Icon aria-hidden className="h-5 w-5" strokeWidth={1.75} />
                </span>
                {i < STEPS.length - 1 && (
                  <span aria-hidden className="hidden h-px flex-1 bg-line md:block" />
                )}
              </div>
              <div>
                <p className="text-xs font-medium text-subtle tabular-nums">Step {i + 1}</p>
                <h3 className="mt-1 text-lg font-semibold tracking-tight">{title}</h3>
                <p className="mt-2 text-[15px] leading-7 text-muted">{body}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
