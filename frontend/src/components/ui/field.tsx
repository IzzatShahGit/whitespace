import type { ComponentProps } from "react";

export function Field({
  label,
  hint,
  id,
  ...props
}: ComponentProps<"input"> & { label: string; hint?: string; id: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm text-sage">
        {label}
      </label>
      <input
        id={id}
        className="h-11 rounded-xl border border-ink-line bg-ink px-4 text-cream transition-colors outline-none placeholder:text-sage-dim/60 focus:border-ember/70 focus:ring-2 focus:ring-ember/20"
        {...props}
      />
      {hint && <p className="text-xs text-sage-dim">{hint}</p>}
    </div>
  );
}
