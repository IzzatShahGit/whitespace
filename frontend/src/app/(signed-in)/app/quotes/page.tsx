import type { Metadata } from "next";
import { Suspense } from "react";

import { QuotesList } from "@/components/quotes/quote-pages";

export const metadata: Metadata = { title: "Quotes · Whitespace" };

export default function QuotesPage() {
  return (
    <Suspense>
      <QuotesList />
    </Suspense>
  );
}
