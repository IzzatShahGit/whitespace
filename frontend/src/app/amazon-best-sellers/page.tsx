import type { Metadata } from "next";
import { Suspense } from "react";

import { Footer } from "@/components/landing/closing-cta";
import { LandingHeader } from "@/components/landing/landing-header";
import { IdeasLanding } from "@/components/ideas/ideas-page";

export const metadata: Metadata = {
  title: "Amazon best sellers this week, and what to sell next · Whitespace",
  description:
    "This week's top 10 Amazon US best sellers in 15 categories, beside official US import growth. Check any product's profit, freight, duty and suppliers. Free, no sign-up.",
};

export default function AmazonBestSellersPage() {
  return (
    <>
      <LandingHeader />
      <main className="flex-1">
        <Suspense>
          <IdeasLanding />
        </Suspense>
      </main>
      <Footer />
    </>
  );
}
