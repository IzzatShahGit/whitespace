import type { Metadata } from "next";

import { BusinessSettings } from "@/components/onboarding/business-settings";

export const metadata: Metadata = { title: "Business preferences · Whitespace" };

export default function BusinessPage() {
  return <BusinessSettings />;
}
