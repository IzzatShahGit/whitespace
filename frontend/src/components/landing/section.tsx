import type { ReactNode } from "react";

/** A landing section's eyebrow, takeaway title and optional lede. */
export function SectionIntro({
  eyebrow,
  title,
  children,
  center = false,
}: {
  eyebrow: string;
  title: ReactNode;
  children?: ReactNode;
  center?: boolean;
}) {
  return (
    <div className={`max-w-2xl ${center ? "mx-auto text-center" : ""}`}>
      <p className="text-sm font-medium text-brand">{eyebrow}</p>
      <h2 className="mt-2 text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
        {title}
      </h2>
      {children && <p className="mt-4 text-lg leading-8 text-pretty text-muted">{children}</p>}
    </div>
  );
}

/** "Example" tag for illustrative figures, so nothing made-up passes as live data. */
export function ExampleTag() {
  return (
    <span className="rounded-full border border-line px-2 py-0.5 text-xs text-subtle">Example</span>
  );
}
