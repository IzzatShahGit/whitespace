import type { Metadata } from "next";
import { Suspense } from "react";

import { NicheView } from "@/components/views/niche-view";
import { Loading } from "@/components/views/states";

// Renders after the session check: see (signed-in)/layout.tsx.
export const instant = false;

export const metadata: Metadata = { title: "Niche · Whitespace" };

export default function NichePage({ params }: PageProps<"/app/browse/[slug]">) {
  return (
    <Suspense fallback={<Loading />}>
      <NicheView params={params} />
    </Suspense>
  );
}
