import type { Metadata } from "next";

import { AdminView } from "@/components/views/admin-view";

export const metadata: Metadata = { title: "Usage · Whitespace" };

export default function AdminPage() {
  return <AdminView />;
}
