import type { Metadata } from "next";

import { TendersView } from "@/components/views/tenders-view";

export const metadata: Metadata = { title: "Tenders · Whitespace" };

export default function TendersPage() {
  return <TendersView />;
}
