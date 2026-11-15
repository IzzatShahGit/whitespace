const steps = [
  {
    n: "01",
    title: "Describe your product",
    body: "Type “cotton towels”, not HS code 630260. We match your words to the right trade codes.",
  },
  {
    n: "02",
    title: "See ranked markets",
    body: "Every importing country, scored on rising demand, rivals losing share, and room for you to grow.",
  },
  {
    n: "03",
    title: "Get the brief",
    body: "An AI analyst explains why the gap exists and what to check before entering, with every number from the data.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="scroll-mt-20 border-t border-ink-line/60">
      <div className="mx-auto max-w-6xl px-6 py-24">
        <h2 className="max-w-xl text-3xl font-semibold tracking-tight sm:text-4xl">
          From a product name to a shortlist <span className="text-sage">in minutes.</span>
        </h2>
        <div className="mt-12 grid gap-5 md:grid-cols-3">
          {steps.map((step) => (
            <article
              key={step.n}
              className="group rounded-2xl border border-ink-line bg-ink-raised p-6 transition-all duration-300 hover:-translate-y-1 hover:border-sage-dim/60"
            >
              <span className="font-mono text-sm text-ember">{step.n}</span>
              <h3 className="mt-4 text-lg font-medium">{step.title}</h3>
              <p className="mt-2 leading-7 text-sage">{step.body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
