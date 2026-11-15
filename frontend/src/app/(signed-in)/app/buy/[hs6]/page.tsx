import type { Metadata } from "next";
import { Suspense } from "react";

import { Loading } from "@/components/views/states";
import { SourcingView } from "@/components/views/sourcing-view";

export const metadata: Metadata = { title: "Where to buy · Whitespace" };

// The product code is only known at request time: render inside a Suspense boundary.
export default function SourcingPage({ params }: PageProps<"/app/buy/[hs6]">) {
  return (
    <Suspense fallback={<Loading />}>
      <SourcingView params={params} />
    </Suspense>
  );
}
