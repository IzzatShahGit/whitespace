import type { Metadata } from "next";

import { AccountSettings } from "@/components/settings/account-settings";

// Renders after the session check: see (signed-in)/layout.tsx.
export const instant = false;

export const metadata: Metadata = { title: "Account · Whitespace" };

export default function AccountPage() {
  return <AccountSettings />;
}
