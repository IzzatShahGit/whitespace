import type { Metadata } from "next";
import { Suspense } from "react";

import { PipelineView } from "@/components/views/pipeline-view";

// Renders after the session check: see (signed-in)/layout.tsx.
export const instant = false;

export const metadata: Metadata = { title: "Pipeline · Whitespace" };

export default function PipelinePage() {
  // Reads ?show= and ?contact= from the URL.
  return (
    <Suspense>
      <PipelineView />
    </Suspense>
  );
}
