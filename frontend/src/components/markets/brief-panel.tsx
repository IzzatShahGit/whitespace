"use client";

import { type ComponentProps, type ReactNode, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { type BriefContent, useBrief, useRequestBrief } from "@/lib/api/queries";

const PROGRESS = [
  "Reading the latest news about this market…",
  "Pulling out facts with their sources…",
  "Checking every figure against the data…",
  "Writing your plan…",
];

function Kind({
  tone,
  children,
}: {
  tone: "measured" | "reported" | "guidance";
  children: string;
}) {
  const styles = {
    measured: "bg-tile-3/30 text-sage",
    reported: "bg-ember/15 text-ember",
    guidance: "bg-ink-line/60 text-sage-dim",
  };
  return (
    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${styles[tone]}`}>
      {children}
    </span>
  );
}

function Section({
  title,
  kind,
  children,
}: {
  title: string;
  kind: ComponentProps<typeof Kind>;
  children: ReactNode;
}) {
  return (
    <section>
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-medium text-cream">{title}</h3>
        <Kind {...kind} />
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
}

/** Citations: fact ids show their figure on hover; claim ids link to the numbered source. */
function Refs({ refs, content }: { refs: string[]; content: BriefContent }) {
  const sourceNumber = (claimId: string) => {
    const claim = content.claims.find((c) => c.id === claimId);
    const index = claim ? content.sources.findIndex((s) => s.id === claim.source) : -1;
    return index >= 0 ? index + 1 : null;
  };
  return (
    <span className="ml-1 inline-flex gap-1 align-middle">
      {refs.map((ref) => {
        if (ref.startsWith("C")) {
          const n = sourceNumber(ref);
          return n ? (
            <a
              key={ref}
              href={`#source-${n}`}
              className="rounded bg-ember/15 px-1 text-[10px] text-ember hover:bg-ember/25"
            >
              {n}
            </a>
          ) : null;
        }
        const fact = content.facts.find((f) => f.id === ref);
        return fact ? (
          <span
            key={ref}
            title={`${fact.label}: ${fact.value}`}
            className="cursor-help rounded bg-tile-3/30 px-1 text-[10px] text-sage"
          >
            data
          </span>
        ) : null;
      })}
    </span>
  );
}

function Points({ points, content }: { points: BriefContent["why_now"]; content: BriefContent }) {
  return (
    <ul className="flex flex-col gap-2">
      {points.map((p) => (
        <li key={p.text} className="flex items-start gap-2 text-sm leading-6 text-sage">
          <span className="mt-2 h-1.5 w-1.5 shrink-0 rotate-45 bg-ember" aria-hidden />
          <span>
            {p.text}
            <Refs refs={p.refs} content={content} />
          </span>
        </li>
      ))}
    </ul>
  );
}

function Progress() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setStep((s) => Math.min(s + 1, PROGRESS.length - 1)), 2500);
    return () => clearInterval(timer);
  }, []);
  return (
    <div role="status" className="flex flex-col gap-3">
      {PROGRESS.map((text, i) => (
        <p
          key={text}
          className={`flex items-center gap-3 text-sm transition-opacity duration-500 ${
            i <= step ? "opacity-100" : "opacity-30"
          }`}
        >
          <span
            className={`h-2 w-2 rounded-full ${
              i < step ? "bg-tile-1" : i === step ? "animate-pulse bg-ember" : "bg-ink-line"
            }`}
          />
          {text}
        </p>
      ))}
    </div>
  );
}

function BriefBody({ content }: { content: BriefContent }) {
  return (
    <div className="flex flex-col gap-7">
      <p className="text-xl leading-8 font-medium text-cream">{content.headline}</p>

      {content.why_now.length > 0 && (
        <Section title="Why now" kind={{ tone: "measured", children: "Measured · customs data" }}>
          <Points points={content.why_now} content={content} />
        </Section>
      )}

      <Section
        title="What's driving it"
        kind={{ tone: "reported", children: "Reported · cited news" }}
      >
        {content.drivers.length > 0 ? (
          <Points points={content.drivers} content={content} />
        ) : (
          <p className="text-sm text-sage-dim">
            {content.research_available
              ? "No recent news clearly explains this market's numbers, so nothing is claimed."
              : "News research wasn't available for this brief."}
          </p>
        )}
      </Section>

      {content.risks.length > 0 && (
        <Section title="Risks" kind={{ tone: "measured", children: "Data and news" }}>
          <Points points={content.risks} content={content} />
        </Section>
      )}

      {content.entry_checks.length > 0 && (
        <Section title="Before you export" kind={{ tone: "guidance", children: "Guidance" }}>
          <ul className="flex flex-col gap-2">
            {content.entry_checks.map((check) => (
              <li key={check} className="flex items-start gap-2.5 text-sm text-sage">
                <span className="mt-0.5 h-4 w-4 shrink-0 rounded border border-ink-line" />
                {check}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {content.roadmap.length > 0 && (
        <Section title="Your roadmap" kind={{ tone: "guidance", children: "Guidance" }}>
          <ol className="flex flex-col gap-4">
            {content.roadmap.map((step, i) => (
              <li key={step.title} className="flex gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-ember/15 font-mono text-xs text-ember">
                  {i + 1}
                </span>
                <span>
                  <span className="block text-sm font-medium text-cream">{step.title}</span>
                  <span className="block text-sm text-sage">{step.detail}</span>
                </span>
              </li>
            ))}
          </ol>
        </Section>
      )}

      {content.sources.length > 0 && (
        <section>
          <h3 className="text-sm font-medium text-cream">Sources</h3>
          <ol className="mt-2 flex flex-col gap-1.5 text-sm">
            {content.sources.map((s, i) => (
              <li key={s.id} id={`source-${i + 1}`} className="flex gap-2 text-sage">
                <span className="font-mono text-xs text-ember">{i + 1}</span>
                <a
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer nofollow"
                  className="underline-offset-4 hover:text-cream hover:underline"
                >
                  {s.title || s.domain}
                </a>
                <span className="shrink-0 text-xs text-sage-dim">
                  {s.domain}
                  {s.published ? ` · ${s.published}` : ""}
                </span>
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}

/** The AI market brief: written on request, from our data plus cited news. */
export function BriefPanel({
  exporter,
  hs6,
  market,
}: {
  exporter: string;
  hs6: string;
  market: string;
}) {
  const brief = useBrief(exporter, hs6, market);
  const request = useRequestBrief(exporter, hs6, market);
  const status = brief.data?.status;

  return (
    <section className="rounded-2xl border border-ember/30 bg-ink-raised p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-medium">AI market brief</h2>
          <p className="text-sm text-sage">
            Our data plus the latest news, turned into a plan. Every figure is checked.
          </p>
        </div>
        {status === "ready" && brief.data?.stale && (
          <Button
            variant="secondary"
            className="h-9 px-4"
            disabled={request.isPending}
            onClick={() => request.mutate()}
          >
            Refresh
          </Button>
        )}
      </div>

      <div className="mt-6">
        {brief.isPending && <p className="text-sm text-sage">Loading…</p>}

        {(status === "missing" || status === "failed") && (
          <div className="flex flex-col items-start gap-3">
            {status === "failed" && <p className="text-sm text-caution">{brief.data?.error}</p>}
            <Button disabled={request.isPending} onClick={() => request.mutate()}>
              {status === "failed" ? "Try again" : "Write my brief"}
            </Button>
            <p className="text-xs text-sage-dim">Takes about 10 seconds.</p>
          </div>
        )}

        {request.isError && (
          <p role="alert" className="mt-3 text-sm text-caution">
            {request.error.message}
          </p>
        )}

        {status === "pending" && <Progress />}

        {status === "ready" && brief.data?.content && (
          <>
            <BriefBody content={brief.data.content} />
            <p className="mt-7 border-t border-ink-line/60 pt-4 text-xs text-sage-dim">
              Written {brief.data.generated_at?.slice(0, 10)}
              {brief.data.usage &&
                ` · ${brief.data.usage.calls} AI calls, ${(
                  brief.data.usage.input_tokens + brief.data.usage.output_tokens
                ).toLocaleString()} tokens`}
              {brief.data.content.removed_points > 0 &&
                ` · ${brief.data.content.removed_points} unsupported point${
                  brief.data.content.removed_points === 1 ? "" : "s"
                } removed by the fact check`}
              . Reported claims come from the linked sources; check them before acting.
            </p>
          </>
        )}
      </div>
    </section>
  );
}
