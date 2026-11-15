import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthForm } from "@/components/auth/auth-form";

export const metadata: Metadata = { title: "Sign in · Whitespace" };

export default function LoginPage() {
  // AuthForm reads ?next= and ?error= from the URL, so it renders in the browser.
  return (
    <Suspense>
      <AuthForm mode="login" />
    </Suspense>
  );
}
