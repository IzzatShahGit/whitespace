import type { Metadata } from "next";
import { Suspense } from "react";

import { DealSheetView } from "@/components/views/deal-sheet-view";
import { Loading } from "@/components/views/states";

export const metadata: Metadata = { title: "Deal sheet · Whitespace" };

export default function DealSheetPage({ params }: PageProps<"/app/markets/[hs6]/[market]/deal">) {
  return (
    <Suspense fallback={<Loading />}>
      <DealSheetView params={params} />
    </Suspense>
  );
}
