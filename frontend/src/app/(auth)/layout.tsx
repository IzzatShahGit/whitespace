import { Check } from "lucide-react";

import { IsoGrid } from "@/components/brand/iso-grid";
import { Logo } from "@/components/brand/logo";

const POINTS = [
  "Every importing country ranked for your product, with a plain verdict",
  "Suppliers compared on price per kg, track record and momentum",
  "An AI guide that answers in your language, checked against the data",
];

/** Sign-in and sign-up: the brand's promise on the left (desktop), the form on the right. */
export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="flex flex-1 lg:grid lg:min-h-dvh lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <aside className="relative hidden flex-col justify-between overflow-hidden border-r border-line bg-surface p-10 lg:flex xl:p-14">
        <div
          aria-hidden
          className="pointer-events-none absolute -bottom-40 -left-32 h-[32rem] w-[32rem] rounded-full bg-brand-soft blur-3xl"
        />
        <Logo />
        <div className="relative max-w-md">
          <IsoGrid animated className="w-40" title="Whitespace: one gap, one opportunity" />
          <p className="mt-8 text-3xl leading-tight font-semibold tracking-tight text-balance">
            Find the countries buying what you make.
          </p>
          <ul className="mt-6 flex flex-col gap-3">
            {POINTS.map((point) => (
              <li key={point} className="flex items-start gap-3 text-[15px] leading-6 text-muted">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-positive-soft text-positive">
                  <Check aria-hidden className="h-3.5 w-3.5" strokeWidth={2.5} />
                </span>
                {point}
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-subtle">
          Customs data from every country (CEPII BACI, 2017–2024), plus monthly EU and US figures.
        </p>
      </aside>
      <main className="flex w-full flex-col px-4 py-6 sm:px-6 lg:px-10">
        <div className="lg:hidden">
          <Logo />
        </div>
        <div className="flex flex-1 items-center justify-center py-10 sm:py-16">{children}</div>
      </main>
    </div>
  );
}
