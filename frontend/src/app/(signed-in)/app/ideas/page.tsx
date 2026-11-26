import type { Metadata } from "next";
import { Suspense } from "react";

import { IdeasPage } from "@/components/ideas/ideas-page";

// Renders after the session check: see (signed-in)/layout.tsx.
export const instant = false;

export const metadata: Metadata = { title: "Product ideas · Whitespace" };

export default function ProductIdeasPage() {
  // The chosen category lives in the URL (?cat=kitchen), so links share it.
  return (
    <Suspense>
      <IdeasPage />
    </Suspense>
  );
}
