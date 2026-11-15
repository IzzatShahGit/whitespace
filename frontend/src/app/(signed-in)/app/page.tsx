import type { Metadata } from "next";

import { Dashboard } from "@/components/views/dashboard";

export const metadata: Metadata = { title: "Your markets · Whitespace" };

export default function DashboardPage() {
  return <Dashboard />;
}
