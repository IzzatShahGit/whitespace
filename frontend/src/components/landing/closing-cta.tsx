import Link from "next/link";
import { IsoGrid } from "@/components/brand/iso-grid";
import { Wordmark } from "@/components/brand/logo";
import { ButtonLink } from "@/components/ui/button";

export function ClosingCta() {
  return (
    <section className="border-t border-line/70">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-6 px-4 py-20 text-center sm:px-6 sm:py-28">
        <span aria-hidden>
          <IsoGrid className="w-28 sm:w-32" />
        </span>
        <h2 className="max-w-2xl text-3xl font-semibold tracking-tight text-balance sm:text-5xl">
          Your next market is a gap no one has filled yet.
        </h2>
        <p className="max-w-lg text-lg leading-8 text-muted">
          Tell us what you make. In a minute you’ll know where it sells, and why.
        </p>
        <div className="flex flex-col items-center gap-3 sm:flex-row">
          <ButtonLink href="/signup" size="lg">
            Start free
          </ButtonLink>
          <ButtonLink href="#try" variant="secondary" size="lg">
            Try it without an account
          </ButtonLink>
        </div>
      </div>
    </section>
  );
}

export function Footer() {
  return (
    <footer className="border-t border-line/70 bg-surface">
      <div className="mx-auto flex max-w-6xl flex-col gap-8 px-4 py-10 sm:px-6 md:flex-row md:justify-between">
        <div className="max-w-sm">
          <Wordmark className="text-lg" />
          <p className="mt-2 text-sm leading-6 text-muted">
            Where to sell, where to buy, from customs data. Guidance, not legal or financial advice.
          </p>
        </div>
        <nav aria-label="Footer" className="grid grid-cols-2 gap-x-12 gap-y-2 text-sm">
          <Link href="/#how-it-works" className="text-muted hover:text-fg">
            How it works
          </Link>
          <Link href="/signup" className="text-muted hover:text-fg">
            Create an account
          </Link>
          <Link href="/#data" className="text-muted hover:text-fg">
            The data
          </Link>
          <Link href="/login" className="text-muted hover:text-fg">
            Sign in
          </Link>
          <Link href="/amazon-best-sellers" className="text-muted hover:text-fg">
            Amazon best sellers
          </Link>
          <Link href="/fba-calculator" className="text-muted hover:text-fg">
            Amazon FBA calculator
          </Link>
          <Link href="/terms" className="text-muted hover:text-fg">
            Terms
          </Link>
          <Link href="/privacy" className="text-muted hover:text-fg">
            Privacy
          </Link>
        </nav>
      </div>
      <p className="mx-auto max-w-6xl px-4 pb-8 text-xs text-subtle sm:px-6">
        Trade data: CEPII BACI, Eurostat, US Census Bureau. © 2026 Whitespace.
      </p>
    </footer>
  );
}
