"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

import { track } from "@/lib/analytics";

/** Counts one page view per route change (path only; the server strips ids). */
export function PageViews() {
  const pathname = usePathname();
  useEffect(() => {
    if (pathname) track("page_view", pathname);
  }, [pathname]);
  return null;
}
