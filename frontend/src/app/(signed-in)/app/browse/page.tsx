import type { Metadata } from "next";
import { Suspense } from "react";

import { BrowseView } from "@/components/views/browse-view";
import { Loading } from "@/components/views/states";

export const metadata: Metadata = { title: "Browse niches · Whitespace" };

export default function BrowsePage() {
  return (
    <Suspense fallback={<Loading />}>
      <BrowseView />
    </Suspense>
  );
}
