import type { ComponentProps } from "react";

export const inputClass =
  "h-11 w-full rounded-xl border border-line bg-surface px-4 text-fg shadow-card transition-colors " +
  "outline-none placeholder:text-subtle focus:border-brand/60 focus:ring-4 focus:ring-brand/10 " +
  "disabled:opacity-60";

export function Field({
  label,
  hint,
  error,
  id,
  className = "",
  ...props
}: ComponentProps<"input"> & { label: string; hint?: string; error?: string; id: string }) {
  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      <label htmlFor={id} className="text-sm font-medium text-fg">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={Boolean(error) || undefined}
        aria-describedby={hint || error ? `${id}-hint` : undefined}
        className={`${inputClass} ${error ? "border-negative/60" : ""}`}
        {...props}
      />
      {(error || hint) && (
        <p id={`${id}-hint`} className={`text-xs ${error ? "text-negative" : "text-subtle"}`}>
          {error ?? hint}
        </p>
      )}
    </div>
  );
}
