import type { Metadata } from "next";

import { QuotesList } from "@/components/quotes/quote-pages";

export const metadata: Metadata = { title: "Quotes · Whitespace" };

export default function QuotesPage() {
  return <QuotesList />;
}
