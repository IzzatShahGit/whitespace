import type { Metadata } from "next";
import { Suspense } from "react";

import { VerifyEmail } from "@/components/auth/email-links";

export const metadata: Metadata = {
  title: "Confirm your email · Whitespace",
  referrer: "no-referrer",
};

export default function VerifyEmailPage() {
  return (
    <Suspense>
      <VerifyEmail />
    </Suspense>
  );
}
