import type { Metadata } from "next";

import { QuoteView } from "@/components/quotes/quote-pages";

export const metadata: Metadata = { title: "Quote · Whitespace" };

export default function QuotePage({ params }: PageProps<"/app/quotes/[id]">) {
  return <QuoteView params={params} />;
}
