"use client";

import { useSyncExternalStore } from "react";

// Steps the server can't see (pages opened, tools tried). Kept in this browser only: a
// convenience for the journey on Home, never account data.

export type Step = "market" | "rules";

const KEY = "ws-steps";
const EVENT = "ws-steps-change";

function read(): Step[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "[]") as Step[];
  } catch {
    return [];
  }
}

export function markStep(step: Step) {
  const steps = read();
  if (steps.includes(step)) return;
  try {
    localStorage.setItem(KEY, JSON.stringify([...steps, step]));
  } catch {
    return; // storage blocked: the checklist just stays as it is
  }
  window.dispatchEvent(new Event(EVENT));
}

function subscribe(onChange: () => void) {
  window.addEventListener(EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

let cache = { raw: "", steps: [] as Step[] };
function snapshot(): Step[] {
  let raw = "";
  try {
    raw = localStorage.getItem(KEY) ?? "";
  } catch {
    raw = "";
  }
  if (raw !== cache.raw) cache = { raw, steps: read() };
  return cache.steps;
}

const EMPTY: Step[] = [];
export function useSteps(): Step[] {
  return useSyncExternalStore(subscribe, snapshot, () => EMPTY);
}
