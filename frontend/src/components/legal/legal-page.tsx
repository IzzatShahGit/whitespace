import Link from "next/link";
import type { ReactNode } from "react";

import { Logo } from "@/components/brand/logo";
import { CONTACT_EMAIL, LEGAL_UPDATED } from "@/lib/site";

/** A readable long-form page for the terms and privacy policy. */
export function LegalPage({
  title,
  intro,
  children,
}: {
  title: string;
  intro: string;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="border-b border-line/70 bg-surface">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-4 sm:px-6">
          <Logo />
          <nav className="flex gap-4 text-sm text-muted">
            <Link href="/terms" className="hover:text-fg">
              Terms
            </Link>
            <Link href="/privacy" className="hover:text-fg">
              Privacy
            </Link>
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-10 sm:px-6 sm:py-14">
        <p className="text-sm text-subtle">Last updated {LEGAL_UPDATED}</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h1>
        <p className="mt-4 text-lg leading-8 text-muted">{intro}</p>
        <div className="legal mt-10 flex flex-col gap-8 text-[15px] leading-7 text-muted [&_a]:text-brand [&_a]:underline [&_a]:underline-offset-4 [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:text-fg [&_li]:ml-5 [&_li]:list-disc [&_strong]:text-fg [&_ul]:mt-2 [&_ul]:flex [&_ul]:flex-col [&_ul]:gap-1.5">
          {children}
        </div>
        <p className="mt-12 border-t border-line pt-6 text-sm text-subtle">
          Questions?{" "}
          {CONTACT_EMAIL ? (
            <>
              Email{" "}
              <a
                href={`mailto:${CONTACT_EMAIL}`}
                className="text-brand underline underline-offset-4"
              >
                {CONTACT_EMAIL}
              </a>
              .
            </>
          ) : (
            "Reply to any email from us."
          )}
        </p>
      </main>
    </div>
  );
}

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2>{title}</h2>
      {children}
    </section>
  );
}
