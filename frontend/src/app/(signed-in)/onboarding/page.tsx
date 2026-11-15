import type { Metadata } from "next";

import { Onboarding } from "@/components/views/onboarding";

export const metadata: Metadata = { title: "Your markets · Whitespace" };

export default function OnboardingPage() {
  return <Onboarding />;
}
