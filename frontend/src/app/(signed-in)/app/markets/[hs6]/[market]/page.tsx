import type { Metadata } from "next";
import { Suspense } from "react";

import { MarketDetailView } from "@/components/views/market-detail-view";
import { Loading } from "@/components/views/states";

export const metadata: Metadata = { title: "Market detail · Whitespace" };

export default function MarketDetailPage({ params }: PageProps<"/app/markets/[hs6]/[market]">) {
  return (
    <Suspense fallback={<Loading />}>
      <MarketDetailView params={params} />
    </Suspense>
  );
}
