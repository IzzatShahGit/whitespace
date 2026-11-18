import type { Metadata } from "next";

import { ForgotPasswordForm } from "@/components/auth/password-reset";

export const metadata: Metadata = { title: "Reset your password · Whitespace" };

export default function ForgotPasswordPage() {
  return <ForgotPasswordForm />;
}
