import type { Metadata } from "next";

import { TendersView } from "@/components/views/tenders-view";

// Renders after the session check: see (signed-in)/layout.tsx.
export const instant = false;

export const metadata: Metadata = { title: "Tenders · Whitespace" };

export default function TendersPage() {
  return <TendersView />;
}
