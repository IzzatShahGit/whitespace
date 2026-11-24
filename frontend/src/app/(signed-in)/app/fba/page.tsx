import type { Metadata } from "next";
import { Suspense } from "react";

import { FbaPage } from "@/components/fba/fba-page";

// Renders after the session check: see (signed-in)/layout.tsx.
export const instant = false;

export const metadata: Metadata = { title: "Sell on Amazon · Whitespace" };

export default function AmazonPage() {
  // The calculator reads its inputs from the URL (?hs6=&from=&price=…), so links share it.
  return (
    <Suspense>
      <FbaPage />
    </Suspense>
  );
}
