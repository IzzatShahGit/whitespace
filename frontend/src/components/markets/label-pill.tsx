import type { MarketItem } from "@/lib/api/queries";

type Label = MarketItem["label"];

// The word always shows: colour supports the label, it never carries it alone.
const styles: Record<Label, string> = {
  Strong: "bg-ember/15 text-ember",
  Good: "bg-tile-2/20 text-sage",
  Watch: "bg-ink-line/70 text-sage-dim",
};

export function LabelPill({ label }: { label: Label }) {
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[label]}`}>
      {label}
    </span>
  );
}

export function SellingBadge() {
  return (
    <span className="rounded-full border border-ink-line px-2.5 py-0.5 text-xs text-sage">
      You sell here
    </span>
  );
}
