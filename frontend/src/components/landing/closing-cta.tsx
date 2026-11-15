import { Wordmark } from "@/components/brand/logo";
import { ButtonLink } from "@/components/ui/button";

export function ClosingCta() {
  return (
    <section className="border-t border-ink-line/60">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-6 px-6 py-24 text-center">
        <h2 className="max-w-2xl text-3xl font-semibold tracking-tight sm:text-4xl">
          Your next market is a gap <span className="text-ember">someone hasn’t filled yet.</span>
        </h2>
        <ButtonLink href="/signup">Create a free account</ButtonLink>
      </div>
      <footer className="border-t border-ink-line/60">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-2 px-6 py-8 text-sm text-sage-dim sm:flex-row">
          <Wordmark className="text-base" />
          <p>Built on public trade data from CEPII BACI.</p>
        </div>
      </footer>
    </section>
  );
}
