import type { Metadata } from "next";
import { Suspense } from "react";

import { BrowseView } from "@/components/views/browse-view";
import { Loading } from "@/components/views/states";

// Renders after the session check: see (signed-in)/layout.tsx.
export const instant = false;

export const metadata: Metadata = { title: "Browse niches · Whitespace" };

export default function BrowsePage() {
  return (
    <Suspense fallback={<Loading />}>
      <BrowseView />
    </Suspense>
  );
}
