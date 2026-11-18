import type { Metadata } from "next";
import { Suspense } from "react";

import { ResetPasswordForm } from "@/components/auth/password-reset";

// The token is in the link; keep it out of referrers sent to other sites.
export const metadata: Metadata = {
  title: "Choose a new password · Whitespace",
  referrer: "no-referrer",
};

export default function ResetPasswordPage() {
  // Reads ?token= from the URL, so it renders in the browser.
  return (
    <Suspense>
      <ResetPasswordForm />
    </Suspense>
  );
}
