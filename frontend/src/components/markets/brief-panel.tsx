"use client";

import {
  Check,
  Database,
  ExternalLink,
  Lightbulb,
  Newspaper,
  RefreshCw,
  Sparkles,
  Square,
} from "lucide-react";
import { type ReactNode, useEffect, useId, useState } from "react";

import { Badge, type Tone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/empty";
import { type BriefContent, useBrief, useRequestBrief } from "@/lib/api/queries";

const PROGRESS = [
  "Reading the latest news about this market…",
  "Pulling out facts with their sources…",
  "Checking every figure against the data…",
  "Writing your plan…",
];

const KINDS: Record<"measured" | "reported" | "guidance", [Tone, ReactNode, string]> = {
  measured: ["brand", <Database key="i" />, "Measured · customs data"],
  reported: ["neutral", <Newspaper key="i" />, "Reported · cited news"],
  guidance: ["neutral", <Lightbulb key="i" />, "Guidance"],
};

function Section({
  title,
  kind,
  children,
}: {
  title: string;
  kind: keyof typeof KINDS;
  children: ReactNode;
}) {
  const [tone, icon, label] = KINDS[kind];
  return (
    <section>
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold text-fg">{title}</h3>
        <Badge tone={tone} icon={icon}>
          {label}
        </Badge>
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
}

/** A "data" chip that shows the figure behind a point (hover, focus or tap). */
function FactRef({ label, value }: { label: string; value: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span className="relative inline-flex">
      <button
        type="button"
        aria-describedby={open ? id : undefined}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen((o) => !o)}
        className="rounded-md bg-brand-soft px-1.5 text-xs font-medium text-brand focus-visible:outline-2 focus-visible:outline-brand"
      >
        data
      </button>
      {open && (
        <span
          id={id}
          role="tooltip"
          className="pop-in absolute bottom-full left-0 z-40 mb-2 w-56 rounded-xl border border-line bg-surface p-3 text-xs leading-5 text-fg shadow-pop"
        >
          <span className="block text-muted">{label}</span>
          <span className="font-medium">{value}</span>
        </span>
      )}
    </span>
  );
}

/** Citations: fact ids show their figure; claim ids link to the numbered source. */
function Refs({ refs, content }: { refs: string[]; content: BriefContent }) {
  const sourceNumber = (claimId: string) => {
    const claim = content.claims.find((c) => c.id === claimId);
    const index = claim ? content.sources.findIndex((s) => s.id === claim.source) : -1;
    return index >= 0 ? index + 1 : null;
  };
  return (
    <span className="ml-1.5 inline-flex gap-1 align-middle">
      {refs.map((ref) => {
        if (ref.startsWith("C")) {
          const n = sourceNumber(ref);
          return n ? (
            <a
              key={ref}
              href={`#source-${n}`}
              aria-label={`Source ${n}`}
              className="rounded-md bg-surface-2 px-1.5 text-xs font-medium text-muted hover:text-fg focus-visible:outline-2 focus-visible:outline-brand"
            >
              {n}
            </a>
          ) : null;
        }
        const fact = content.facts.find((f) => f.id === ref);
        return fact ? <FactRef key={ref} label={fact.label} value={fact.value} /> : null;
      })}
    </span>
  );
}

function Points({ points, content }: { points: BriefContent["why_now"]; content: BriefContent }) {
  return (
    <ul className="flex flex-col gap-2.5">
      {points.map((p) => (
        <li key={p.text} className="flex items-start gap-2.5 text-sm leading-6 text-muted">
          <span className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" aria-hidden />
          <span dir="auto">
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
    <ol role="status" className="flex flex-col gap-3">
      {PROGRESS.map((text, i) => (
        <li
          key={text}
          className={`flex items-center gap-3 text-sm transition-opacity duration-300 ${
            i <= step ? "text-fg" : "text-subtle opacity-60"
          }`}
        >
          <span
            className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full ${
              i < step
                ? "bg-brand text-on-brand"
                : i === step
                  ? "border-2 border-brand"
                  : "border border-line-strong"
            }`}
          >
            {i < step && <Check className="h-3 w-3" strokeWidth={3} />}
          </span>
          {text}
        </li>
      ))}
    </ol>
  );
}

function BriefBody({ content }: { content: BriefContent }) {
  return (
    <div className="flex flex-col gap-7">
      <p dir="auto" className="text-lg leading-7 font-medium text-pretty text-fg">
        {content.headline}
      </p>

      {content.why_now.length > 0 && (
        <Section title="Why now" kind="measured">
          <Points points={content.why_now} content={content} />
        </Section>
      )}

      <Section title="What’s driving it" kind="reported">
        {content.drivers.length > 0 ? (
          <Points points={content.drivers} content={content} />
        ) : (
          <p className="text-sm text-subtle">
            {content.research_available
              ? "No recent news clearly explains this market’s numbers, so nothing is claimed."
              : "News research wasn’t available for this brief."}
          </p>
        )}
      </Section>

      {content.risks.length > 0 && (
        <Section title="Risks" kind="measured">
          <Points points={content.risks} content={content} />
        </Section>
      )}

      {content.entry_checks.length > 0 && (
        <Section title="Before you export" kind="guidance">
          <ul className="flex flex-col gap-2">
            {content.entry_checks.map((check) => (
              <li key={check} dir="auto" className="flex items-start gap-2.5 text-sm text-muted">
                <Square className="mt-0.5 h-4 w-4 shrink-0 text-subtle" aria-hidden />
                {check}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {content.roadmap.length > 0 && (
        <Section title="Your roadmap" kind="guidance">
          <ol className="flex flex-col gap-4">
            {content.roadmap.map((step, i) => (
              <li key={step.title} className="flex gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-soft text-xs font-semibold text-brand tabular-nums">
                  {i + 1}
                </span>
                <span dir="auto">
                  <span className="block text-sm font-medium text-fg">{step.title}</span>
                  <span className="block text-sm text-muted">{step.detail}</span>
                </span>
              </li>
            ))}
          </ol>
        </Section>
      )}

      {content.sources.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-fg">Sources</h3>
          <ol className="mt-2 flex flex-col gap-2 text-sm">
            {content.sources.map((s, i) => (
              <li key={s.id} id={`source-${i + 1}`} className="flex gap-2.5 text-muted">
                <span className="w-4 shrink-0 text-xs leading-5 font-medium text-subtle tabular-nums">
                  {i + 1}
                </span>
                <span className="min-w-0">
                  <a
                    href={s.url}
                    target="_blank"
                    rel="noopener noreferrer nofollow"
                    className="inline-flex items-center gap-1 rounded text-fg underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-brand"
                  >
                    {s.title || s.domain}
                    <ExternalLink className="h-3.5 w-3.5 shrink-0 text-subtle" aria-hidden />
                  </a>
                  <span className="block text-xs text-subtle">
                    {s.domain}
                    {s.published ? ` · ${s.published}` : ""}
                  </span>
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
  marketName,
}: {
  exporter: string;
  hs6: string;
  market: string;
  marketName?: string;
}) {
  const brief = useBrief(exporter, hs6, market);
  const request = useRequestBrief(exporter, hs6, market);
  const status = brief.data?.status;

  return (
    <Card className="p-5 sm:p-6">
      <CardHeader
        icon={<Sparkles />}
        title="AI market brief"
        description="Our data plus the latest news, turned into a plan. Every figure is checked."
        action={
          status === "ready" && brief.data?.stale ? (
            <Button
              variant="secondary"
              size="sm"
              disabled={request.isPending}
              onClick={() => request.mutate()}
            >
              <RefreshCw /> Refresh
            </Button>
          ) : undefined
        }
      />

      <div className="mt-6">
        {brief.isPending && (
          <div className="flex flex-col gap-3" aria-busy>
            <Skeleton className="h-6 w-3/4" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
          </div>
        )}

        {brief.isError && (
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-sm text-muted">Couldn’t check for a brief.</p>
            <Button variant="secondary" size="sm" onClick={() => void brief.refetch()}>
              Try again
            </Button>
          </div>
        )}

        {(status === "missing" || status === "failed") && (
          <div className="flex flex-col gap-4 rounded-2xl border border-dashed border-line-strong/60 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
            <div>
              <p className="font-medium">
                {status === "failed"
                  ? "The last brief couldn’t be written"
                  : `Get a written plan for ${marketName ?? "this market"}`}
              </p>
              <p className="mt-1 text-sm text-muted">
                {status === "failed"
                  ? (brief.data?.error ?? "Please try again.")
                  : "Why now, what’s driving demand, the risks, and the steps to a first shipment. Takes about 10 seconds."}
              </p>
            </div>
            <Button
              variant="secondary"
              className="shrink-0"
              disabled={request.isPending}
              onClick={() => request.mutate()}
            >
              <Sparkles /> {status === "failed" ? "Try again" : "Write my brief"}
            </Button>
          </div>
        )}

        {request.isError && (
          <p role="alert" className="mt-3 text-sm text-negative">
            {request.error.message}
          </p>
        )}

        {status === "pending" && <Progress />}

        {status === "ready" && brief.data?.content && (
          <>
            <BriefBody content={brief.data.content} />
            <p className="mt-7 border-t border-line pt-4 text-xs leading-5 text-subtle">
              Written {brief.data.generated_at?.slice(0, 10)}. Every figure is checked against
              customs data
              {brief.data.content.removed_points > 0 &&
                `; ${brief.data.content.removed_points} unsupported point${
                  brief.data.content.removed_points === 1 ? " was" : "s were"
                } removed`}
              . Reported claims come from the linked sources: check them before acting.
            </p>
          </>
        )}
      </div>
    </Card>
  );
}
