"use client";

import { useCallback, useSyncExternalStore } from "react";

import { THEME_KEY as KEY } from "@/lib/theme-script";

// Light, dark, or follow the device. Stored per browser (a viewer convenience, not account data).
export type ThemeChoice = "light" | "dark" | "system";

const EVENT = "ws-theme-change";

function read(): ThemeChoice {
  try {
    const value = localStorage.getItem(KEY);
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}

function subscribe(onChange: () => void) {
  window.addEventListener(EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

export function useTheme(): [ThemeChoice, (choice: ThemeChoice) => void] {
  const choice = useSyncExternalStore(subscribe, read, () => "system" as const);
  const set = useCallback((next: ThemeChoice) => {
    try {
      if (next === "system") localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, next);
    } catch {
      // storage blocked: the choice still applies for this page view
    }
    if (next === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = next;
    window.dispatchEvent(new Event(EVENT));
  }, []);
  return [choice, set];
}
