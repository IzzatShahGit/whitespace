import Link from "next/link";

import { IsoGrid } from "./iso-grid";

export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`tracking-tight ${className}`}>
      <span className="font-bold text-fg">white</span>
      <span className="font-light text-muted">space</span>
    </span>
  );
}

export function Logo({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="group flex items-center gap-2.5" aria-label="Whitespace home">
      <IsoGrid className="h-8 w-auto transition-transform duration-300 group-hover:-translate-y-0.5" />
      <Wordmark className="text-xl" />
    </Link>
  );
}
