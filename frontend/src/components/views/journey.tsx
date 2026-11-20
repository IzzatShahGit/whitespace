"use client";

import { ArrowRight, Check } from "lucide-react";
import Link from "next/link";

import { ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { usePipeline } from "@/lib/api/pipeline";
import { useQuotes } from "@/lib/api/quotes";
import { useShipments } from "@/lib/api/shipments";
import { useWatches } from "@/lib/api/watch";
import { useT } from "@/lib/i18n";
import { useSteps } from "@/lib/steps";

type StepKey = "market" | "rules" | "buyers" | "check" | "quote" | "ship";
type Step = { key: StepKey; href: string; done: boolean; detail?: string };

/**
 * The path from "where do I sell?" to "it's shipped", as six steps. Each step's state
 * comes from what the user has actually done (pipeline, checks, quotes, shipments), and
 * the first step not done is the one to do now, with the page's one primary button.
 */
export function Journey({ market, marketName }: { market?: string; marketName?: string }) {
  const t = useT();
  const steps = useSteps();
  const watches = useWatches();
  const pipeline = usePipeline();
  const quotes = useQuotes();
  const shipments = useShipments();
  if (pipeline.isPending || quotes.isPending || shipments.isPending) return null;

  const contacts = pipeline.data ?? [];
  const checked = contacts.filter((c) => c.check_verdict).length;
  const nQuotes = quotes.data?.length ?? 0;
  const nShipments = shipments.data?.length ?? 0;
  const base = market ?? "/app/markets";
  // Doing a later step means the earlier ones were done some other way.
  const reached = nShipments ? 6 : nQuotes ? 5 : checked ? 4 : contacts.length ? 3 : 0;
  const list: Step[] = [
    {
      key: "market",
      href: base,
      done: reached > 0 || steps.includes("market") || Boolean(watches.data?.length),
      detail: marketName,
    },
    { key: "rules", href: `${base}?tab=needs`, done: reached > 1 || steps.includes("rules") },
    {
      key: "buyers",
      href: contacts.length ? "/app/pipeline" : `${base}?tab=buyers`,
      done: contacts.length > 0,
      detail: contacts.length ? t("journey.inPipeline", { count: contacts.length }) : undefined,
    },
    {
      key: "check",
      href: contacts.length ? "/app/pipeline" : "/app/check",
      done: reached > 3,
      detail: checked ? t("journey.checked", { count: checked }) : undefined,
    },
    {
      key: "quote",
      href: nQuotes ? "/app/quotes" : "/app/quotes/new",
      done: reached > 4,
      detail: nQuotes ? t("journey.quotes", { count: nQuotes }) : undefined,
    },
    { key: "ship", href: "/app/shipments", done: reached > 5 },
  ];
  const current = list.findIndex((s) => !s.done);
  if (current === -1) return null; // the whole path is walked: nothing to guide
  const now = list[current];

  return (
    <Card className="rise-in flex flex-col gap-5 p-5 sm:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-medium text-muted">
            {t("journey.title")} ·{" "}
            {t("journey.progress", { step: current + 1, total: list.length })}
          </p>
          <h2 className="mt-1 text-lg font-semibold tracking-tight">
            {t(`journey.steps.${now.key}.next`, { market: marketName ?? "" })}
          </h2>
          <p className="mt-0.5 text-sm text-muted">{t(`journey.steps.${now.key}.why`)}</p>
        </div>
        <ButtonLink href={now.href} className="self-start sm:self-auto">
          {t(`journey.steps.${now.key}.cta`)} <ArrowRight />
        </ButtonLink>
      </div>

      <ol className="grid grid-cols-1 gap-2 sm:grid-cols-3 xl:grid-cols-6">
        {list.map((step, i) => {
          const state = step.done ? "done" : i === current ? "now" : "later";
          return (
            <li key={step.key} className="min-w-0">
              <Link
                href={step.href}
                aria-current={state === "now" ? "step" : undefined}
                className={`flex h-full items-start gap-2.5 rounded-xl border p-3 transition-colors ${
                  state === "now"
                    ? "border-brand/60 bg-brand-soft"
                    : "border-line hover:border-line-strong hover:bg-surface-2"
                }`}
              >
                <span
                  className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold tabular-nums ${
                    state === "done"
                      ? "bg-positive text-white"
                      : state === "now"
                        ? "bg-brand text-on-brand"
                        : "bg-surface-2 text-subtle"
                  }`}
                >
                  {state === "done" ? <Check className="h-3.5 w-3.5" aria-hidden /> : i + 1}
                </span>
                <span className="min-w-0">
                  <span
                    className={`block text-sm font-medium ${state === "later" ? "text-muted" : "text-fg"}`}
                  >
                    {t(`journey.steps.${step.key}.title`)}
                  </span>
                  <span className="block truncate text-xs text-muted">
                    {step.detail ?? t(`journey.steps.${step.key}.hint`)}
                  </span>
                </span>
              </Link>
            </li>
          );
        })}
      </ol>
    </Card>
  );
}
