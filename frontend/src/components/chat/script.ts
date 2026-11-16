// Text written by people or the model can be in any language and direction.

// Letters Urdu uses and Arabic and Persian don't (ٹ ڈ ڑ ں ھ ہ ے ۓ), so Arabic text from
// Egypt or Morocco keeps its own (Naskh) font.
const URDU = /[ٹڈڑںھہےۓ]/;

export const isUrdu = (text: string) => URDU.test(text);

const URDU_CLASS =
  "[font-family:var(--font-urdu),var(--font-geist-sans),system-ui,sans-serif] leading-[2.1]";

/**
 * Props for any element showing user- or model-written text: direction, language, and
 * for Urdu the Nastaliq font with room for its tall letters (instead of `leading`).
 */
export function scriptProps(text: string, className = "", leading = "") {
  const urdu = isUrdu(text);
  return {
    dir: "auto" as const,
    lang: urdu ? "ur" : undefined,
    className: `${className} ${urdu ? URDU_CLASS : leading}`.trim(),
  };
}
