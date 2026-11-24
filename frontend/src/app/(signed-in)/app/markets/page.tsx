import type { Metadata } from "next";

import { SellView } from "@/components/views/sell-view";

// Renders after the session check: see (signed-in)/layout.tsx.
export const instant = false;

export const metadata: Metadata = { title: "Where to sell · Whitespace" };

export default function SellPage() {
  return <SellView />;
}
