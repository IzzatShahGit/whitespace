import type { Metadata } from "next";
import { Suspense } from "react";

import { QuoteBuilder } from "@/components/quotes/quote-builder";

export const metadata: Metadata = { title: "New quote · Whitespace" };

export default function NewQuotePage() {
  // Reads ?hs6=&market=&price=&kg=&contact=&buyer= from deal sheets and the pipeline.
  return (
    <Suspense>
      <QuoteBuilder />
    </Suspense>
  );
}
