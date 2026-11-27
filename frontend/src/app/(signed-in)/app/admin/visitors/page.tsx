import type { Metadata } from "next";
import { Suspense } from "react";

import { VisitorsView } from "@/components/admin/visitors-view";

// Renders after the session check: see (signed-in)/layout.tsx.
export const instant = false;

export const metadata: Metadata = { title: "Visitors · Admin · Whitespace" };

export default function AdminVisitorsPage() {
  // Reads ?show=, ?country=, ?source=, ?test= and ?page= from the URL.
  return (
    <Suspense>
      <VisitorsView />
    </Suspense>
  );
}
