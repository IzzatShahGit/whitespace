// First-party usage analytics (see the backend's services/analytics.py and visits.py).
// No cookies and nothing stored in the browser. The server turns these reports into
// visits: where they came from, country, device, pages in order and engaged time.
// Fire-and-forget; never blocks or throws. "Do Not Track" / GPC turn it all off.
import type { components } from "@/lib/api/schema";

export type TrackedEvent = components["schemas"]["EventIn"]["event"];
type EventBody = components["schemas"]["EventIn"];

const TICK = 5; // seconds between engagement checks
const IDLE_MS = 120_000; // no input for 2 minutes: not engaged any more
const REPORT_EVERY = 60; // send engaged time at least once a minute (keeps "live now" true)
const UNTRACKED = /^\/app\/admin(\/|$)/; // admins browsing their own stats

function optedOut(): boolean {
  const nav = navigator as Navigator & { globalPrivacyControl?: boolean };
  return nav.doNotTrack === "1" || nav.globalPrivacyControl === true;
}

function send(payload: EventBody): void {
  try {
    const body = JSON.stringify(payload);
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

/** A key action (deal sheet printed, email opened, ...). */
export function track(event: TrackedEvent, path?: string): void {
  if (typeof window === "undefined" || optedOut()) return;
  send({ event, path: path ?? window.location.pathname });
}

// ---------- page views and engaged time ----------
let firstView = true;
let currentPath: string | null = null;
let engaged = 0; // seconds on currentPath not yet reported
let lastInput = 0;
let started = false;

function reportEngaged(): void {
  if (currentPath && engaged >= 1) {
    send({ event: "engage", path: currentPath, seconds: Math.round(engaged) });
  }
  engaged = 0;
}

function startEngagement(): void {
  if (started) return;
  started = true;
  lastInput = Date.now();
  const onInput = () => {
    lastInput = Date.now();
  };
  for (const name of ["pointerdown", "pointermove", "keydown", "scroll", "wheel", "touchstart"]) {
    window.addEventListener(name, onInput, { passive: true, capture: true });
  }
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") reportEngaged();
    else lastInput = Date.now();
  });
  window.addEventListener("pagehide", reportEngaged);
  window.setInterval(() => {
    if (document.visibilityState !== "visible" || Date.now() - lastInput > IDLE_MS) return;
    engaged += TICK;
    if (engaged >= REPORT_EVERY) reportEngaged();
  }, TICK * 1000);
}

/** One page view per route change. The first one in a tab says where the visit came from. */
export function trackPageView(path: string): void {
  try {
    if (typeof window === "undefined" || optedOut()) return;
    reportEngaged(); // time on the page they're leaving
    if (UNTRACKED.test(path)) {
      currentPath = null;
      return;
    }
    currentPath = path;
    const body: EventBody = { event: "page_view", path };
    if (firstView) {
      firstView = false;
      const query = new URLSearchParams(window.location.search);
      if (document.referrer) body.referrer = document.referrer.slice(0, 500);
      const source = query.get("utm_source") ?? query.get("ref");
      if (source) body.utm_source = source.slice(0, 100);
      const campaign = query.get("utm_campaign");
      if (campaign) body.utm_campaign = campaign.slice(0, 100);
    }
    send(body);
    startEngagement();
  } catch {
    // Counting must never break the page.
  }
}
