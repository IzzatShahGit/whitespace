import type { Metadata } from "next";
import { Suspense } from "react";

import { FbaLanding } from "@/components/fba/fba-page";
import { Footer } from "@/components/landing/closing-cta";
import { LandingHeader } from "@/components/landing/landing-header";

export const metadata: Metadata = {
  title: "Free Amazon FBA profit calculator · Whitespace",
  description:
    "Will your product make money on Amazon US? Supplier price, sea freight, the 2026 US tariffs and Amazon's FBA fees in one answer. Free, no sign-up.",
};

export default function FbaCalculatorPage() {
  return (
    <>
      <LandingHeader />
      <main className="flex-1">
        <Suspense>
          <FbaLanding />
        </Suspense>
      </main>
      <Footer />
    </>
  );
}
