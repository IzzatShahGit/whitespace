import type { Metadata } from "next";

import { Dashboard } from "@/components/views/dashboard";

// Renders after the session check: see (signed-in)/layout.tsx.
export const instant = false;

export const metadata: Metadata = { title: "Your markets · Whitespace" };

export default function DashboardPage() {
  return <Dashboard />;
}
