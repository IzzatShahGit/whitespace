import { CloudOff, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";

/** A section that failed to load: what happened, and a retry. */
export function LoadError({
  title,
  children,
  onRetry,
  retrying = false,
  action,
}: {
  title: string;
  children?: ReactNode;
  onRetry?: () => void;
  retrying?: boolean;
  action?: ReactNode;
}) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center gap-3 rounded-2xl border border-line bg-surface px-6 py-10 text-center shadow-card"
    >
      <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-negative-soft text-negative">
        <CloudOff className="h-6 w-6" aria-hidden />
      </span>
      <h2 className="text-base font-semibold">{title}</h2>
      {children && <p className="max-w-sm text-sm text-muted">{children}</p>}
      <div className="flex flex-wrap justify-center gap-2">
        {onRetry && (
          <Button variant="secondary" onClick={onRetry} disabled={retrying}>
            <RefreshCw className={retrying ? "animate-spin" : undefined} /> Try again
          </Button>
        )}
        {action}
      </div>
    </div>
  );
}
