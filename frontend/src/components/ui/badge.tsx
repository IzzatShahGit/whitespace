import type { ReactNode } from "react";

export type Tone = "positive" | "negative" | "neutral" | "brand" | "accent" | "caution";

/** One mapping from meaning to colour, used by every chip, badge and callout. */
export const toneClass: Record<Tone, string> = {
  positive: "bg-positive-soft text-positive",
  negative: "bg-negative-soft text-negative",
  neutral: "bg-surface-2 text-muted",
  brand: "bg-brand-soft text-brand",
  accent: "bg-accent-soft text-accent-strong",
  caution: "bg-caution-soft text-caution",
};

/** Colour always comes with words (and usually an icon), never alone. */
export function Badge({
  tone = "neutral",
  icon,
  children,
  size = "sm",
}: {
  tone?: Tone;
  icon?: ReactNode;
  children: ReactNode;
  size?: "sm" | "md";
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full font-medium whitespace-nowrap ${toneClass[tone]} ${
        size === "md"
          ? "px-3 py-1 text-sm [&>svg]:h-4 [&>svg]:w-4"
          : "px-2 py-0.5 text-xs [&>svg]:h-3.5 [&>svg]:w-3.5"
      }`}
    >
      {icon}
      {children}
    </span>
  );
}

/** A tinted box for a sentence that matters (verdicts, warnings). */
export function Callout({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <div className={`rounded-xl px-4 py-3 text-sm leading-6 ${toneClass[tone]}`}>{children}</div>
  );
}
