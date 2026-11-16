"use client";

import { CircleCheck, Circle, Flag, X } from "lucide-react";
import Link from "next/link";

import { Card, CardHeader } from "@/components/ui/card";
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

  return (
    <Card className="rise-in flex flex-col gap-4 p-5 sm:p-6">
      <CardHeader
        icon={<Flag />}
        title="Get the most from Whitespace"
        description={`${done} of ${items.length} done. Each takes under a minute.`}
        action={
          <button
            type="button"
            aria-label="Hide this checklist"
            onClick={() => markStep("dismissed")}
            className="rounded-lg p-1.5 text-subtle hover:bg-surface-2 hover:text-fg"
          >
            <X className="h-4 w-4" />
          </button>
        }
      />
      <div className="h-1.5 overflow-hidden rounded-full bg-surface-2">
        <div
          className="h-full rounded-full bg-brand transition-[width] duration-500"
          style={{ width: `${(done / items.length) * 100}%` }}
        />
      </div>
      <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
        {items.map((item) => (
          <li key={item.title}>
            <Link
              href={item.href}
              className={`flex h-full items-start gap-2 rounded-xl border p-3 text-sm transition-colors ${
                item.done
                  ? "border-transparent bg-positive-soft text-positive"
                  : "border-line hover:border-brand/40"
              }`}
            >
              {item.done ? (
                <CircleCheck className="mt-0.5 h-4 w-4 shrink-0" />
              ) : (
                <Circle className="mt-0.5 h-4 w-4 shrink-0 text-subtle" />
              )}
              {item.title}
            </Link>
          </li>
        ))}
      </ol>
    </Card>
  );
}
