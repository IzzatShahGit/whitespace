import type { Metadata } from "next";

import { BusinessSettings } from "@/components/onboarding/business-settings";

// Renders after the session check: see (signed-in)/layout.tsx.
export const instant = false;

export const metadata: Metadata = { title: "Business preferences · Whitespace" };

export default function BusinessPage() {
  return <BusinessSettings />;
}
