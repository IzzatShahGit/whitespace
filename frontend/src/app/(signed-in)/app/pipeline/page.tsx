import type { Metadata } from "next";
import { Suspense } from "react";

import { PipelineView } from "@/components/views/pipeline-view";

export const metadata: Metadata = { title: "Pipeline · Whitespace" };

export default function PipelinePage() {
  // Reads ?show= and ?contact= from the URL.
  return (
    <Suspense>
      <PipelineView />
    </Suspense>
  );
}
