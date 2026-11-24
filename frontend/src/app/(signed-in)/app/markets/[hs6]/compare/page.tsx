import type { Metadata } from "next";
import { Suspense } from "react";

import { CompareView } from "@/components/views/compare-view";
import { Loading } from "@/components/views/states";

// Renders after the session check: see (signed-in)/layout.tsx.
export const instant = false;

export const metadata: Metadata = { title: "Compare markets · Whitespace" };

// The product and markets come from the URL (?m=DEU,GBR), known only at request time.
export default function ComparePage({ params }: PageProps<"/app/markets/[hs6]/compare">) {
  return (
    <Suspense fallback={<Loading />}>
      <CompareView params={params} />
    </Suspense>
  );
}
