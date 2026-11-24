import type { Metadata } from "next";

import { BuyView } from "@/components/views/buy-view";

// Renders after the session check: see (signed-in)/layout.tsx.
export const instant = false;

export const metadata: Metadata = { title: "Where to buy · Whitespace" };

export default function BuyPage() {
  return <BuyView />;
}
