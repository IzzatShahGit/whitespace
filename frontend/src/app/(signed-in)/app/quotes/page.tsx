import type { Metadata } from "next";
import { Suspense } from "react";

import { QuotesList } from "@/components/quotes/quote-pages";

// Renders after the session check: see (signed-in)/layout.tsx.
export const instant = false;

export const metadata: Metadata = { title: "Quotes · Whitespace" };

export default function QuotesPage() {
  return (
    <Suspense>
      <QuotesList />
    </Suspense>
  );
}
