"use client";

import { CircleCheck, Circle, Flag, X } from "lucide-react";
import Link from "next/link";

import { Card } from "@/components/ui/card";
import { useChatThreads } from "@/lib/api/queries";
import { useWatches } from "@/lib/api/watch";
import { markStep, useSteps } from "@/lib/steps";

/** Five first wins that show what Whitespace can do; disappears once done (or dismissed). */
export function GettingStarted({ firstProduct }: { firstProduct?: string }) {
  const steps = useSteps();
  const watches = useWatches();
  const threads = useChatThreads();
  const marketHref = firstProduct ? `/app/markets/${firstProduct}` : "/app/markets";

  const items = [
    { done: true, title: "Tell us what you sell", href: "/app/settings/business" },
    { done: steps.includes("market"), title: "Open a market’s full analysis", href: marketHref },
    {
      done: Boolean(watches.data?.length),
      title: "Watch a market for alerts",
      href: marketHref,
    },
    { done: steps.includes("price"), title: "Check your price in your currency", href: marketHref },
    { done: Boolean(threads.data?.length), title: "Ask Whitespace a question", href: "/app/ask" },
  ];
  const done = items.filter((i) => i.done).length;
  if (steps.includes("dismissed") || done === items.length) return null;
  if (watches.isPending || threads.isPending) return null;

  // One slim row: progress, the steps as chips, dismiss. Present, never in the way.
  return (
    <Card className="rise-in relative flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:gap-5">
      <div className="flex shrink-0 items-center gap-3">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-soft text-brand">
          <Flag className="h-4 w-4" aria-hidden />
        </span>
        <div>
          <p className="text-sm font-semibold">Getting started</p>
          <p className="text-xs text-muted tabular-nums">
            {done} of {items.length} done
          </p>
        </div>
      </div>
      <ol className="flex min-w-0 flex-1 flex-wrap gap-1.5">
        {items
          .filter((item) => !item.done)
          .map((item) => (
            <li key={item.title}>
              <Link
                href={item.href}
                className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs transition-colors ${
                  item.done
                    ? "text-positive line-through decoration-positive/40"
                    : "border border-line text-fg hover:border-brand/50 hover:text-brand"
                }`}
              >
                {item.done ? (
                  <CircleCheck className="h-3.5 w-3.5 shrink-0" aria-hidden />
                ) : (
                  <Circle className="h-3.5 w-3.5 shrink-0 text-subtle" aria-hidden />
                )}
                {item.title}
              </Link>
            </li>
          ))}
      </ol>
      <button
        type="button"
        aria-label="Hide this checklist"
        onClick={() => markStep("dismissed")}
        className="absolute top-2 right-2 rounded-lg p-1.5 text-subtle hover:bg-surface-2 hover:text-fg sm:static"
      >
        <X className="h-4 w-4" />
      </button>
    </Card>
  );
}
