import type { ReactNode } from "react";

/** What to show when there's nothing yet: say why, and what to do next. */
export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon: ReactNode;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-line-strong bg-surface/50 px-6 py-12 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-soft text-brand [&>svg]:h-6 [&>svg]:w-6">
        {icon}
      </span>
      <h3 className="text-base font-semibold">{title}</h3>
      {children && <p className="max-w-sm text-sm text-muted">{children}</p>}
      {action}
    </div>
  );
}

/** Grey placeholder blocks while data loads (shimmers unless motion is reduced). */
export function Skeleton({ className = "h-24" }: { className?: string }) {
  return <div aria-hidden className={`skeleton ${className}`} />;
}
