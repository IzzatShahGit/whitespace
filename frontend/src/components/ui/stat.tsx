import type { ReactNode } from "react";

import { InfoTip } from "@/components/ui/info-tip";

/** A headline number with its label, an optional change, and an optional explanation. */
export function Stat({
  label,
  value,
  change,
  changeTone = "neutral",
  note,
  explain,
  icon,
}: {
  label: string;
  value: ReactNode;
  change?: string;
  changeTone?: "positive" | "negative" | "neutral";
  note?: ReactNode;
  explain?: string;
  icon?: ReactNode;
}) {
  const changeColor =
    changeTone === "positive"
      ? "text-positive"
      : changeTone === "negative"
        ? "text-negative"
        : "text-muted";
  return (
    <div className="rounded-2xl border border-line bg-surface p-4 shadow-card sm:p-5">
      <p className="flex items-center gap-1.5 text-xs font-medium text-muted">
        {icon && <span className="text-subtle [&>svg]:h-3.5 [&>svg]:w-3.5">{icon}</span>}
        {label}
        {explain && <InfoTip text={explain} />}
      </p>
      <p className="mt-2 text-2xl font-semibold tracking-tight tabular-nums">{value}</p>
      {(change || note) && (
        <p className="mt-1 text-xs text-muted">
          {change && <span className={`font-medium ${changeColor}`}>{change}</span>}
          {change && note && " · "}
          {note}
        </p>
      )}
    </div>
  );
}
