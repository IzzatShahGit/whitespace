import type { Metadata } from "next";
import { Suspense } from "react";

import { NicheView } from "@/components/views/niche-view";
import { Loading } from "@/components/views/states";

export const metadata: Metadata = { title: "Niche · Whitespace" };

export default function NichePage({ params }: PageProps<"/app/browse/[slug]">) {
  return (
    <Suspense fallback={<Loading />}>
      <NicheView params={params} />
    </Suspense>
  );
}
