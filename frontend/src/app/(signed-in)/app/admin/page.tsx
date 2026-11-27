import type { Metadata } from "next";

import { AdminView } from "@/components/views/admin-view";

// Renders after the session check: see (signed-in)/layout.tsx.
export const instant = false;

export const metadata: Metadata = { title: "Admin · Whitespace" };

export default function AdminPage() {
  return <AdminView />;
}
