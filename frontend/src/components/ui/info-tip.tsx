"use client";

import { Info } from "lucide-react";
import { useId, useState } from "react";

/** Explains a term in place (hover, focus or tap), so jargon never blocks anyone. */
export function InfoTip({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span className="relative inline-flex">
      <button
        type="button"
        aria-label="What does this mean?"
        aria-describedby={open ? id : undefined}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen((o) => !o)}
        className="rounded-full text-subtle transition-colors hover:text-fg focus-visible:outline-2 focus-visible:outline-brand"
      >
        <Info className="h-3.5 w-3.5" />
      </button>
      {open && (
        <span
          id={id}
          role="tooltip"
          className="pop-in absolute bottom-full left-1/2 z-40 mb-2 w-60 -translate-x-1/2 rounded-xl border border-line bg-surface p-3 text-xs leading-5 font-normal text-fg shadow-pop"
        >
          {text}
        </span>
      )}
    </span>
  );
}
