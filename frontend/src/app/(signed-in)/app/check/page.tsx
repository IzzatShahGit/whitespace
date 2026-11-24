import type { Metadata } from "next";
import { Suspense } from "react";

import { CheckView } from "@/components/checks/buyer-check";

// Renders after the session check: see (signed-in)/layout.tsx.
export const instant = false;

export const metadata: Metadata = { title: "Check · Whitespace" };

export default function CheckPage() {
  // Reads ?tab= and ?quote= from the URL.
  return (
    <Suspense>
      <CheckView />
    </Suspense>
  );
}
