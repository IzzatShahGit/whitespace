import { ClosingCta, Footer } from "@/components/landing/closing-cta";
import { Features } from "@/components/landing/features";
import { Hero } from "@/components/landing/hero";
import { HowItWorks } from "@/components/landing/how-it-works";
import { LandingHeader } from "@/components/landing/landing-header";
import { Trust } from "@/components/landing/trust";

export default function Home() {
  return (
    <>
      <LandingHeader />
      <main className="flex-1">
        <Hero />
        <HowItWorks />
        <Features />
        <Trust />
        <ClosingCta />
      </main>
      <Footer />
    </>
  );
}
