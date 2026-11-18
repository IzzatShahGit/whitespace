// First-party usage counts: no cookies, nothing that identifies a person (see the
// backend's services/analytics.py). Fire-and-forget; never blocks or throws.
import type { components } from "@/lib/api/schema";

export type TrackedEvent = components["schemas"]["EventIn"]["event"];

function optedOut(): boolean {
  const nav = navigator as Navigator & { globalPrivacyControl?: boolean };
  return nav.doNotTrack === "1" || nav.globalPrivacyControl === true;
}

export function track(event: TrackedEvent, path?: string): void {
  try {
    if (typeof window === "undefined" || optedOut()) return;
    const body = JSON.stringify({ event, path: path ?? window.location.pathname });
    const blob = new Blob([body], { type: "application/json" });
    if (!navigator.sendBeacon?.("/api/v1/events", blob)) {
      void fetch("/api/v1/events", {
        method: "POST",
        body,
        keepalive: true,
        headers: { "content-type": "application/json" },
      }).catch(() => {});
    }
  } catch {
    // Counting must never break the page.
  }
}
