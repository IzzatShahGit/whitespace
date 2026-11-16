"use client";

import {
  Calculator,
  Check,
  FileText,
  ListChecks,
  type LucideIcon,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

type Step = { key: string; title: string; text: string; icon: LucideIcon };

const STEPS: Step[] = [
  {
    key: "shortlist",
    title: "Shortlist",
    text: "Pick two or three countries from the comparison: one cheap, one established.",
    icon: ListChecks,
  },
  {
    key: "find",
    title: "Find exporters",
    text: "Ask each country’s trade promotion office or chamber of commerce for verified exporters.",
    icon: Search,
  },
  {
    key: "quotes",
    title: "Compare quotes",
    text: "Request samples and FOB quotes. Anything far below the prices here deserves questions.",
    icon: FileText,
  },
  {
    key: "landed",
    title: "Check landed cost",
    text: "Add freight, insurance and your import duty before you decide.",
    icon: Calculator,
  },
  {
    key: "pay",
    title: "Pay safely",
    text: "Start with a small order, paid by letter of credit or escrow.",
    icon: ShieldCheck,
  },
];

const storageKey = (id: string) => `ws-buy-steps-${id}`;

function load(id: string): string[] {
  try {
    const value = JSON.parse(localStorage.getItem(storageKey(id)) ?? "[]");
    return Array.isArray(value) ? value : [];
  } catch {
    return [];
  }
}

/**
 * What to do after choosing where to buy, as a checklist people can tick off.
 * Ticks are a per-browser convenience (kept per product), not account data.
 */
export function NextSteps({ id, askHref }: { id: string; askHref: string }) {
  const [done, setDone] = useState<string[]>(() => (typeof window === "undefined" ? [] : load(id)));

  function toggle(key: string) {
    const next = done.includes(key) ? done.filter((k) => k !== key) : [...done, key];
    setDone(next);
    try {
      localStorage.setItem(storageKey(id), JSON.stringify(next));
    } catch {
      // storage blocked: ticks still work for this visit
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted" aria-live="polite">
        {done.length} of {STEPS.length} done
      </p>
      <ol className="grid gap-0 lg:grid-cols-5 lg:gap-4">
        {STEPS.map((step, i) => {
          const checked = done.includes(step.key);
          const Icon = step.icon;
          return (
            <li key={step.key} className="relative flex gap-4 pb-6 last:pb-0 lg:flex-col lg:pb-0">
              {/* The line joining the steps: down on phones, across on desktop. */}
              {i < STEPS.length - 1 && (
                <span
                  aria-hidden
                  className="absolute top-11 bottom-1 left-[1.375rem] w-px bg-line lg:top-[1.375rem] lg:right-[-1rem] lg:bottom-auto lg:left-12 lg:h-px lg:w-auto"
                />
              )}
              <button
                type="button"
                role="checkbox"
                aria-checked={checked}
                aria-label={`${step.title}: mark as ${checked ? "not done" : "done"}`}
                onClick={() => toggle(step.key)}
                className={`relative flex h-11 w-11 shrink-0 items-center justify-center rounded-full border transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${
                  checked
                    ? "border-positive bg-positive text-surface"
                    : "border-line bg-surface text-muted hover:border-line-strong hover:text-fg"
                }`}
              >
                {checked ? (
                  <Check className="pop-in h-5 w-5" strokeWidth={2.5} />
                ) : (
                  <Icon className="h-5 w-5" strokeWidth={1.75} />
                )}
              </button>
              <div className="min-w-0 pt-1 lg:pt-0">
                <p className="text-xs font-medium text-subtle tabular-nums">Step {i + 1}</p>
                <p
                  className={`text-sm font-medium ${checked ? "text-muted line-through decoration-line-strong" : ""}`}
                >
                  {step.title}
                </p>
                <p className="mt-1 text-sm leading-6 text-muted">{step.text}</p>
                {step.key === "find" && (
                  <Link
                    href={askHref}
                    className="mt-1.5 inline-flex items-center gap-1.5 text-sm font-medium text-brand hover:underline"
                  >
                    <Sparkles className="h-4 w-4" /> Ask how
                  </Link>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
