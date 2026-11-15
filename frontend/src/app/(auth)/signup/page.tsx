import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthForm } from "@/components/auth/auth-form";

export const metadata: Metadata = { title: "Create account · Whitespace" };

export default function SignupPage() {
  // AuthForm reads ?next= and ?error= from the URL, so it renders in the browser.
  return (
    <Suspense>
      <AuthForm mode="signup" />
    </Suspense>
  );
}
