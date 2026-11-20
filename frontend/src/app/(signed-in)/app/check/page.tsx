import type { Metadata } from "next";
import { Suspense } from "react";

import { CheckView } from "@/components/checks/buyer-check";

export const metadata: Metadata = { title: "Check · Whitespace" };

export default function CheckPage() {
  // Reads ?tab= and ?quote= from the URL.
  return (
    <Suspense>
      <CheckView />
    </Suspense>
  );
}
