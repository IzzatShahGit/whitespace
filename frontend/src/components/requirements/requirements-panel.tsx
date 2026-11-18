"use client";

import {
  BadgeCheck,
  ClipboardCheck,
  ExternalLink,
  FileText,
  Landmark,
  RefreshCw,
  Search,
  ShieldCheck,
  Tag,
  TestTubeDiagonal,
} from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/empty";
import {
  type Requirement,
  type RequirementSource,
  type RequirementsOut,
  useRequestRequirements,
  useRequirements,
  useTickRequirement,
} from "@/lib/api/requirements";

const GROUPS: { key: Requirement["category"][]; title: string; icon: ReactNode }[] = [
  { key: ["document", "registration"], title: "Papers and registrations", icon: <FileText /> },
  { key: ["certificate"], title: "Certificates and proof of origin", icon: <BadgeCheck /> },
  { key: ["product_rule"], title: "Rules the goods must meet", icon: <TestTubeDiagonal /> },
  { key: ["labelling"], title: "Labels and marking", icon: <Tag /> },
  { key: ["other"], title: "Other", icon: <ClipboardCheck /> },
];

const NEED: Record<Requirement["need"], { label: string; tone: "caution" | "neutral" | "brand" }> =
  {
    required: { label: "Required", tone: "caution" },
    often_asked: { label: "Buyers ask for it", tone: "brand" },
    depends: { label: "Depends", tone: "neutral" },
  };

const STEPS = [
  "Searching official trade and customs sites…",
  "Reading the rules for your product…",
  "Checking every item against the words on its page…",
];

function Progress() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 7000);
    return () => clearInterval(id);
  }, []);
  return (
    <div aria-live="polite" className="flex flex-col gap-3">
      <p className="text-sm text-muted">{STEPS[step]}</p>
      <Skeleton className="h-14 w-full" />
      <Skeleton className="h-14 w-full" />
      <Skeleton className="h-14 w-4/5" />
    </div>
  );
}

function Item({
  item,
  source,
  done,
  onToggle,
}: {
  item: Requirement;
  source: RequirementSource | undefined;
  done: boolean;
  onToggle: (done: boolean) => void;
}) {
  const id = `req-${item.key}`;
  return (
    <li className="flex gap-3 rounded-xl border border-line p-3.5 transition-colors has-[:checked]:bg-surface-2/50">
      <input
        id={id}
        type="checkbox"
        checked={done}
        onChange={(e) => onToggle(e.target.checked)}
        className="mt-0.5 h-4.5 w-4.5 shrink-0 accent-[var(--color-brand)]"
      />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <label
            htmlFor={id}
            className={`text-sm font-medium ${done ? "text-muted line-through" : "text-fg"}`}
          >
            {item.title}
          </label>
          <Badge tone={NEED[item.need].tone}>{NEED[item.need].label}</Badge>
        </div>
        <p className="mt-1 text-sm leading-6 text-muted">{item.detail}</p>
        {item.issuer && (
          <p className="mt-1 flex items-center gap-1.5 text-xs text-subtle">
            <Landmark className="h-3.5 w-3.5" aria-hidden /> {item.issuer}
          </p>
        )}
        <details className="group mt-2 text-xs">
          <summary className="cursor-pointer text-subtle hover:text-fg">
            What the source says
          </summary>
          <blockquote className="mt-2 border-l-2 border-line-strong pl-3 leading-5 text-muted italic">
            “{item.quote}”
          </blockquote>
          {source && (
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-flex items-center gap-1 text-brand underline-offset-4 hover:underline"
            >
              {source.official && <ShieldCheck className="h-3.5 w-3.5" aria-hidden />}
              {source.domain}
              <ExternalLink className="h-3 w-3" aria-hidden />
              <span className="sr-only">(opens in a new tab)</span>
            </a>
          )}
        </details>
      </div>
    </li>
  );
}

function Checklist({
  data,
  onToggle,
}: {
  data: RequirementsOut;
  onToggle: (item: string, done: boolean) => void;
}) {
  const content = data.content!;
  const done = new Set(data.done ?? []);
  const sources = new Map(content.sources.map((s) => [s.id, s]));
  const total = content.items.length;
  const ticked = content.items.filter((i) => done.has(i.key)).length;
  const official = content.sources.filter((s) => s.official).length;

  if (total === 0) {
    return (
      <p className="text-sm text-muted">
        We couldn’t find rules for this product on official pages we could verify. Ask your importer
        or a customs broker which documents they need.
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-6">
      <div>
        <div className="flex items-baseline justify-between text-sm">
          <span className="font-medium">
            {ticked} of {total} done
          </span>
          <span className="text-xs text-subtle">
            {official} of {content.sources.length} sources are official sites
          </span>
        </div>
        <div
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={total}
          aria-valuenow={ticked}
          aria-label="Requirements done"
          className="mt-2 h-1.5 rounded-full bg-surface-2"
        >
          <div
            className="h-full rounded-full bg-brand transition-[width] duration-500"
            style={{ width: `${(ticked / total) * 100}%` }}
          />
        </div>
      </div>
      {GROUPS.map((group) => {
        const items = content.items.filter((i) => group.key.includes(i.category));
        if (!items.length) return null;
        return (
          <section key={group.title} className="flex flex-col gap-2.5">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-fg [&>svg]:h-4 [&>svg]:w-4 [&>svg]:text-subtle">
              {group.icon} {group.title}
            </h3>
            <ul className="flex flex-col gap-2">
              {items.map((item) => (
                <Item
                  key={item.key}
                  item={item}
                  source={sources.get(item.source)}
                  done={done.has(item.key)}
                  onToggle={(value) => onToggle(item.key, value)}
                />
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

/**
 * What it takes to ship a product into a market, researched on official sites, each
 * item backed by the words on its page; the user ticks items off as they go.
 */
export function RequirementsPanel({
  hs6,
  market,
  marketName,
  exporter,
  exporterName,
  productName,
}: {
  hs6: string;
  market: string;
  marketName: string;
  exporter: string;
  exporterName: string;
  productName: string;
}) {
  const reqs = useRequirements(hs6, market, exporter);
  const request = useRequestRequirements(hs6, market, exporter);
  const tick = useTickRequirement(hs6, market, exporter);
  const data = reqs.data;
  const status = data?.status;

  return (
    <Card className="p-5 sm:p-6">
      <CardHeader
        icon={<ClipboardCheck />}
        title={`What you need to ship to ${marketName}`}
        description={`Papers, certificates, product rules and labels for ${productName} from ${exporterName}.`}
        action={
          data?.content && (data.stale || status === "failed") ? (
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
        {reqs.isPending && <Skeleton className="h-32 w-full" />}
        {reqs.isError && (
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-sm text-muted">Couldn’t load the requirements.</p>
            <Button variant="secondary" size="sm" onClick={() => void reqs.refetch()}>
              Try again
            </Button>
          </div>
        )}
        {(status === "missing" || (status === "failed" && !data?.content)) && (
          <div className="flex flex-col gap-4 rounded-2xl border border-dashed border-line-strong/60 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
            <div>
              <p className="font-medium">
                {status === "failed"
                  ? "The last check didn’t finish"
                  : `Check the rules for ${productName} in ${marketName}`}
              </p>
              <p className="mt-1 text-sm text-muted">
                {status === "failed"
                  ? (data?.error ?? "Please try again.")
                  : "We read official trade and customs sites and keep only items we can quote word for word from the page. About 30 seconds."}
              </p>
            </div>
            <Button
              variant="secondary"
              className="shrink-0"
              disabled={request.isPending}
              onClick={() => request.mutate()}
            >
              <Search /> {status === "failed" ? "Try again" : "Check requirements"}
            </Button>
          </div>
        )}
        {request.isError && (
          <p role="alert" className="mt-3 text-sm text-negative">
            {request.error.message}
          </p>
        )}
        {status === "pending" && <Progress />}
        {status === "failed" && data?.content && (
          <p className="mb-4 text-sm text-muted">
            Couldn’t refresh just now; showing the last check.
          </p>
        )}
        {(status === "ready" || status === "failed") && data?.content && (
          <>
            <Checklist data={data} onToggle={(item, done) => tick.mutate({ item, done })} />
            {tick.isError && (
              <p role="alert" className="mt-3 text-sm text-negative">
                {tick.error.message}
              </p>
            )}
            <p className="mt-7 flex gap-2 border-t border-line pt-4 text-xs leading-5 text-subtle">
              <ShieldCheck className="h-4 w-4 shrink-0" aria-hidden />
              <span>
                Checked {data.generated_at?.slice(0, 10)}. Each item quotes the page it comes from.
                Rules change: confirm with your importer, customs broker or chamber of commerce
                before you ship.
              </span>
            </p>
          </>
        )}
      </div>
    </Card>
  );
}
