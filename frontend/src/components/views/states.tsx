import Link from "next/link";
import type { ReactNode } from "react";

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" className="flex flex-1 items-center justify-center py-24 text-sm text-sage">
      {label}
    </div>
  );
}

export function Problem({
  title,
  children,
  action,
}: {
  title: string;
  children?: ReactNode;
  action?: { href: string; label: string };
}) {
  return (
    <div className="mx-auto flex max-w-md flex-1 flex-col items-center justify-center gap-3 py-24 text-center">
      <h1 className="text-xl font-semibold">{title}</h1>
      {children && <p className="text-sm text-sage">{children}</p>}
      {action && (
        <Link href={action.href} className="text-sm text-ember underline-offset-4 hover:underline">
          {action.label}
        </Link>
      )}
    </div>
  );
}

export function DataNote({ start, end }: { start: number; end: number }) {
  return (
    <p className="text-xs text-sage-dim">
      Customs data {start}–{end} (CEPII BACI). Rankings use measured trade only.
    </p>
  );
}
