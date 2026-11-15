import type { Metadata } from "next";

import { AppShell } from "@/components/auth/app-shell";

export const metadata: Metadata = { title: "Your markets · Whitespace" };

export default function AppPage() {
  return <AppShell />;
}
