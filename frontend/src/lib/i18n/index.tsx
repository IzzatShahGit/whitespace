"use client";

import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
} from "react";

import { en, type MessageKey, type Messages } from "@/lib/i18n/en";
import { DEFAULT_LOCALE, dirOf, isLocale, type Locale, STORAGE_KEY } from "@/lib/i18n/locales";

type Vars = Record<string, string | number>;
type Translate = (key: MessageKey, vars?: Vars) => string;

type Ctx = { locale: Locale; setLocale: (next: Locale) => void; t: Translate };

// Each language is its own chunk, loaded only when chosen.
const LOADERS: Record<Exclude<Locale, "en">, () => Promise<{ default: unknown }>> = {
  ur: () => import("@/lib/i18n/messages/ur.json"),
  bn: () => import("@/lib/i18n/messages/bn.json"),
  vi: () => import("@/lib/i18n/messages/vi.json"),
  tr: () => import("@/lib/i18n/messages/tr.json"),
  es: () => import("@/lib/i18n/messages/es.json"),
  pt: () => import("@/lib/i18n/messages/pt.json"),
  id: () => import("@/lib/i18n/messages/id.json"),
  ar: () => import("@/lib/i18n/messages/ar.json"),
};

function lookup(messages: unknown, key: string): string | undefined {
  let node: unknown = messages;
  for (const part of key.split(".")) {
    if (node === null || typeof node !== "object") return undefined;
    node = (node as Record<string, unknown>)[part];
  }
  return typeof node === "string" ? node : undefined;
}

export function format(template: string, vars?: Vars): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (hole, name: string) =>
    name in vars ? String(vars[name]) : hole,
  );
}

// The chosen language lives outside React (this device's storage, plus memory when storage
// is blocked), read with useSyncExternalStore: the server and the first client render use
// English, then the saved choice applies without a hydration mismatch.
const listeners = new Set<() => void>();
let memory: Locale | null = null;

function readSaved(): Locale {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (isLocale(saved)) return saved;
  } catch {
    // storage blocked: fall back to memory
  }
  return memory ?? DEFAULT_LOCALE;
}

function subscribe(onChange: () => void): () => void {
  listeners.add(onChange);
  window.addEventListener("storage", onChange); // another tab changed it
  return () => {
    listeners.delete(onChange);
    window.removeEventListener("storage", onChange);
  };
}

function saveLocale(next: Locale): void {
  memory = next;
  try {
    localStorage.setItem(STORAGE_KEY, next);
  } catch {
    // kept in memory for this visit; the account keeps it across devices
  }
  listeners.forEach((notify) => notify());
}

const I18n = createContext<Ctx>({
  locale: DEFAULT_LOCALE,
  setLocale: () => {},
  t: (key, vars) => format(lookup(en, key) ?? key, vars),
});

/** Interface language for the whole app: English until another is chosen. */
export function I18nProvider({ children }: { children: ReactNode }) {
  const locale = useSyncExternalStore(subscribe, readSaved, () => DEFAULT_LOCALE);
  const [loaded, setLoaded] = useState<{ locale: Locale; messages: Messages } | null>(null);
  const messages = loaded?.locale === locale ? loaded.messages : null;

  useEffect(() => {
    const root = document.documentElement;
    root.lang = locale;
    root.dir = dirOf(locale);
    if (locale === "en") return;
    let live = true;
    LOADERS[locale]()
      .then((mod) => live && setLoaded({ locale, messages: mod.default as Messages }))
      .catch(() => {}); // English until the language loads
    return () => {
      live = false;
    };
  }, [locale]);

  const setLocale = useCallback((next: Locale) => saveLocale(next), []);
  const t = useCallback<Translate>(
    (key, vars) => format(lookup(messages, key) ?? lookup(en, key) ?? key, vars),
    [messages],
  );
  const value = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);
  return <I18n.Provider value={value}>{children}</I18n.Provider>;
}

export function useT(): Translate {
  return useContext(I18n).t;
}

export function useLocale(): Pick<Ctx, "locale" | "setLocale"> {
  const { locale, setLocale } = useContext(I18n);
  return { locale, setLocale };
}
