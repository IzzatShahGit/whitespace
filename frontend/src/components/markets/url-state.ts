"use client";

import { useCallback, useSyncExternalStore } from "react";

/**
 * Update query parameters in place (no navigation, no new history entry), keeping the
 * others, e.g. an advisor's `?exporter=`. Next.js keeps useSearchParams in sync.
 */
export function replaceSearchParams(changes: Record<string, string | null>): void {
  const params = new URLSearchParams(window.location.search);
  for (const [key, value] of Object.entries(changes)) {
    if (value) params.set(key, value);
    else params.delete(key);
  }
  const query = params.toString();
  window.history.replaceState(null, "", query ? `?${query}` : window.location.pathname);
}

/** Whether a CSS media query matches (false on the server). */
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const list = window.matchMedia(query);
      list.addEventListener("change", onChange);
      return () => list.removeEventListener("change", onChange);
    },
    [query],
  );
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(query).matches,
    () => false,
  );
}
