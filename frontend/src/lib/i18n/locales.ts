/** Interface languages. Buyer-facing documents (quotes, invoices) stay in English, the
 * language of international trade paperwork. */
export const LOCALES = [
  { code: "en", name: "English", english: "English", dir: "ltr" },
  { code: "ur", name: "اردو", english: "Urdu", dir: "rtl" },
  { code: "bn", name: "বাংলা", english: "Bengali", dir: "ltr" },
  { code: "vi", name: "Tiếng Việt", english: "Vietnamese", dir: "ltr" },
  { code: "tr", name: "Türkçe", english: "Turkish", dir: "ltr" },
  { code: "es", name: "Español", english: "Spanish", dir: "ltr" },
  { code: "pt", name: "Português", english: "Portuguese", dir: "ltr" },
  { code: "id", name: "Bahasa Indonesia", english: "Indonesian", dir: "ltr" },
  { code: "ar", name: "العربية", english: "Arabic", dir: "rtl" },
] as const;

export type Locale = (typeof LOCALES)[number]["code"];
export const DEFAULT_LOCALE: Locale = "en";
export const STORAGE_KEY = "ws_lang";

export const isLocale = (value: unknown): value is Locale => LOCALES.some((l) => l.code === value);

export const dirOf = (locale: Locale) => LOCALES.find((l) => l.code === locale)?.dir ?? "ltr";

/** Runs before first paint: sets <html lang dir> from the saved choice, so right-to-left
 * pages don't flip after loading. Must never throw. */
export const LOCALE_SCRIPT = `(function(){try{var l=localStorage.getItem("${STORAGE_KEY}");var r={ur:1,ar:1};if(l){document.documentElement.lang=l;document.documentElement.dir=r[l]?"rtl":"ltr";}}catch(e){}})();`;
