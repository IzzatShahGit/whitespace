import type { Metadata } from "next";

import { QuoteView } from "@/components/quotes/quote-pages";

// Renders after the session check: see (signed-in)/layout.tsx.
export const instant = false;

export const metadata: Metadata = { title: "Quote · Whitespace" };

export default function QuotePage({ params }: PageProps<"/app/quotes/[id]">) {
  return <QuoteView params={params} />;
}
