"use client";

import Link from "next/link";
import { type ReactNode, useEffect, useId, useRef, useState } from "react";

/**
 * A button that opens a floating panel (menus, notifications). Closes on outside
 * click, Escape (focus returns to the button), or choosing an item.
 */
export function Popover({
  label,
  button,
  children,
  align = "end",
  width = "w-64",
}: {
  label: string;
  button: (open: boolean) => ReactNode;
  children: (close: () => void) => ReactNode;
  align?: "start" | "end";
  width?: string;
}) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const id = useId();

  useEffect(() => {
    if (!open) return;
    function onPointer(e: PointerEvent) {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setOpen(false);
        trigger.current?.focus();
      }
    }
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const close = () => setOpen(false);

  return (
    <div ref={root} className="relative">
      <button
        ref={trigger}
        type="button"
        aria-label={label}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((o) => !o)}
        className="rounded-full outline-none focus-visible:ring-2 focus-visible:ring-brand/50"
      >
        {button(open)}
      </button>
      {open && (
        <div
          id={id}
          className={`pop-in absolute top-full z-50 mt-2 ${width} ${
            align === "end" ? "right-0 origin-top-right" : "left-0 origin-top-left"
          } rounded-2xl border border-line bg-surface p-1.5 shadow-pop`}
        >
          {children(close)}
        </div>
      )}
    </div>
  );
}

export function MenuItem({
  icon,
  children,
  onClick,
  href,
  danger = false,
}: {
  icon?: ReactNode;
  children: ReactNode;
  onClick?: () => void;
  href?: string;
  danger?: boolean;
}) {
  const className = `flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-sm transition-colors ${
    danger ? "text-negative hover:bg-negative-soft" : "text-fg hover:bg-surface-2"
  }`;
  const content = (
    <>
      {icon && <span className="text-muted [&>svg]:h-4 [&>svg]:w-4">{icon}</span>}
      {children}
    </>
  );
  return href ? (
    <Link href={href} onClick={onClick} className={className}>
      {content}
    </Link>
  ) : (
    <button type="button" onClick={onClick} className={className}>
      {content}
    </button>
  );
}
