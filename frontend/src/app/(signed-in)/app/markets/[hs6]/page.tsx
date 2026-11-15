import type { Metadata } from "next";
import { Suspense } from "react";

import { MarketsView } from "@/components/views/markets-view";
import { Loading } from "@/components/views/states";

export const metadata: Metadata = { title: "Ranked markets · Whitespace" };

// The product code is only known at request time, so the view renders in a Suspense
// boundary (required for dynamic params with Cache Components).
export default function MarketsPage({ params }: PageProps<"/app/markets/[hs6]">) {
  return (
    <Suspense fallback={<Loading />}>
      <MarketsView params={params} />
    </Suspense>
  );
}
