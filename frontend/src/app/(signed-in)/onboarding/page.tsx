import type { Metadata } from "next";

import { Onboarding } from "@/components/views/onboarding";

// Renders after the session check: see (signed-in)/layout.tsx.
export const instant = false;

export const metadata: Metadata = { title: "Set up · Whitespace" };

export default function OnboardingPage() {
  return <Onboarding />;
}
