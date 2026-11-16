import type { Metadata } from "next";

import { SellView } from "@/components/views/sell-view";

export const metadata: Metadata = { title: "Where to sell · Whitespace" };

export default function SellPage() {
  return <SellView />;
}
