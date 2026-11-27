"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

import { trackPageView } from "@/lib/analytics";

/** One page view per route change, plus engaged time on each page (see lib/analytics). */
export function PageViews() {
  const pathname = usePathname();
  useEffect(() => {
    if (pathname) trackPageView(pathname);
  }, [pathname]);
  return null;
}
