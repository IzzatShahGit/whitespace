import { Noto_Nastaliq_Urdu } from "next/font/google";

// Urdu reads best in Nastaliq. Only the Arabic-script subset, and only fetched when such
// text is on screen (no preload). No metric fallback face, so Latin text in the same
// line falls through to Geist.
export const urduFont = Noto_Nastaliq_Urdu({
  subsets: ["arabic"],
  variable: "--font-urdu",
  display: "swap",
  preload: false,
  adjustFontFallback: false,
});
