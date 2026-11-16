import { Check, Database } from "lucide-react";

import { SectionIntro } from "@/components/landing/section";

const NUMBERS = [
  { value: "235", label: "countries and territories" },
  { value: "5,000+", label: "products, by customs code" },
  { value: "8 years", label: "of yearly trade, 2017–2024" },
  { value: "Monthly", label: "EU and US figures" },
];

const SOURCES = [
  {
    name: "CEPII BACI",
    what: "Every country’s imports and exports, reconciled from UN Comtrade customs reports",
    when: "Yearly, 2017–2024",
  },
  {
    name: "Eurostat Comext",
    what: "Monthly imports into the 27 EU countries, by supplier",
    when: "Monthly",
  },
  {
    name: "US Census Bureau",
    what: "Monthly imports into the United States, by supplier",
    when: "Monthly",
  },
  { name: "ExchangeRate-API", what: "Exchange rates for 166 currencies", when: "Daily" },
];

const PROMISES = [
  "Rankings and verdicts use measured trade only. Nothing is estimated.",
  "Data cards are built from the database, never written by the AI.",
  "Every figure in an AI answer is matched against the data before you see it.",
  "Every page says which year its numbers are from.",
];

export function Trust() {
  return (
    <section id="data" className="scroll-mt-16 border-t border-line/70 bg-surface">
      <div className="mx-auto grid max-w-6xl gap-12 px-4 py-16 sm:px-6 sm:py-24 lg:grid-cols-[1fr_1.1fr] lg:gap-16">
        <div>
          <SectionIntro eyebrow="The data" title="Every figure comes from customs records.">
            Not surveys, not guesses: what countries actually bought and sold, as declared at the
            border.
          </SectionIntro>
          <ul className="mt-8 flex flex-col gap-3">
            {PROMISES.map((text) => (
              <li key={text} className="flex items-start gap-3 text-[15px] leading-6">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-positive-soft text-positive">
                  <Check aria-hidden className="h-3.5 w-3.5" strokeWidth={2.5} />
                </span>
                {text}
              </li>
            ))}
          </ul>
        </div>
        <div className="flex flex-col gap-4">
          <dl className="grid grid-cols-2 gap-3">
            {NUMBERS.map((n) => (
              <div
                key={n.label}
                className="flex flex-col rounded-2xl border border-line bg-canvas p-4 sm:p-5"
              >
                <dt className="text-xs font-medium text-muted">{n.label}</dt>
                <dd className="order-first mb-1 text-2xl font-semibold tracking-tight tabular-nums sm:text-3xl">
                  {n.value}
                </dd>
              </div>
            ))}
          </dl>
          <div className="rounded-2xl border border-line">
            <p className="flex items-center gap-2 border-b border-line px-4 py-3 text-sm font-medium sm:px-5">
              <Database aria-hidden className="h-4 w-4 text-brand" /> Sources
            </p>
            <ul className="divide-y divide-line">
              {SOURCES.map((s) => (
                <li key={s.name} className="flex flex-col gap-0.5 px-4 py-3 sm:px-5">
                  <span className="flex items-baseline justify-between gap-3">
                    <span className="text-sm font-medium">{s.name}</span>
                    <span className="shrink-0 text-xs text-subtle">{s.when}</span>
                  </span>
                  <span className="text-sm text-muted">{s.what}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
