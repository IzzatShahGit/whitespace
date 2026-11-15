import type { Metadata } from "next";

import { BuyView } from "@/components/views/buy-view";

export const metadata: Metadata = { title: "Where to buy · Whitespace" };

export default function BuyPage() {
  return <BuyView />;
}
