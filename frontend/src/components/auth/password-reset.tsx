"use client";

import { CircleAlert, LoaderCircle, MailCheck } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, type ReactNode, useState } from "react";

import { PasswordField } from "@/components/auth/password-field";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { forgotPassword, resetPassword } from "@/lib/auth";

const linkClass = "font-medium text-brand underline-offset-4 hover:underline";

function Shell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <div className="rise-in w-full max-w-sm">
      <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
      <p className="mt-2 text-muted">{subtitle}</p>
      <div className="mt-8">{children}</div>
      <p className="mt-8 text-center text-sm text-muted">
        Remembered it?{" "}
        <Link href="/login" className={linkClass}>
          Sign in
        </Link>
      </p>
    </div>
  );
}

function Problem({ children }: { children: ReactNode }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2.5 rounded-xl bg-negative-soft px-3.5 py-3 text-sm leading-5 text-negative"
    >
      <CircleAlert aria-hidden className="mt-px h-4 w-4 shrink-0" />
      <span>{children}</span>
    </div>
  );
}

/** Step 1: email a one-time link. */
export function ForgotPasswordForm() {
  const [sentTo, setSentTo] = useState<string>();
  const [error, setError] = useState<string>();
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(undefined);
    setPending(true);
    const email = String(new FormData(event.currentTarget).get("email")).trim();
    const result = await forgotPassword(email);
    setPending(false);
    if (result.error) setError(result.error);
    else setSentTo(email);
  }

  if (sentTo) {
    return (
      <Shell
        title="Check your email"
        subtitle="If there’s an account for that address, a link is on its way."
      >
        <div className="flex items-start gap-3 rounded-xl bg-positive-soft p-4 text-sm leading-6 text-positive">
          <MailCheck aria-hidden className="mt-0.5 h-5 w-5 shrink-0" />
          <p>
            We sent a reset link to <strong className="break-all">{sentTo}</strong>. It works once,
            for 30 minutes. Nothing there? Check spam, or{" "}
            <button
              type="button"
              className="underline underline-offset-4"
              onClick={() => setSentTo(undefined)}
            >
              try again
            </button>
            .
          </p>
        </div>
      </Shell>
    );
  }

  return (
    <Shell
      title="Reset your password"
      subtitle="Enter your email and we’ll send you a link to choose a new one."
    >
      <form onSubmit={onSubmit} className="flex flex-col gap-4" aria-busy={pending}>
        <Field
          id="email"
          name="email"
          type="email"
          label="Email"
          autoComplete="email"
          inputMode="email"
          required
        />
        {error && <Problem>{error}</Problem>}
        <Button type="submit" size="lg" disabled={pending} className="mt-2 w-full">
          {pending && <LoaderCircle aria-hidden className="animate-spin" />}
          {pending ? "Sending…" : "Send reset link"}
        </Button>
      </form>
    </Shell>
  );
}

/** Step 2: from the emailed link, choose a new password (and get signed in). */
export function ResetPasswordForm() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const [error, setError] = useState<string>();
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(undefined);
    const form = new FormData(event.currentTarget);
    const password = String(form.get("password"));
    if (password !== String(form.get("confirm"))) {
      setError("The two passwords don’t match.");
      return;
    }
    setPending(true);
    const result = await resetPassword(token, password);
    if (result.error) {
      setError(result.error);
      setPending(false);
      return;
    }
    router.replace("/app");
    router.refresh();
  }

  if (token.length < 20) {
    return (
      <Shell
        title="This link isn’t complete"
        subtitle="Open the link from the email again, or ask for a new one."
      >
        <Link href="/forgot-password" className={linkClass}>
          Send a new reset link
        </Link>
      </Shell>
    );
  }

  return (
    <Shell
      title="Choose a new password"
      subtitle="You’ll be signed in, and signed out everywhere else."
    >
      <form onSubmit={onSubmit} className="flex flex-col gap-4" aria-busy={pending}>
        <PasswordField
          id="password"
          name="password"
          label="New password"
          autoComplete="new-password"
          hint="At least 8 characters."
          minLength={8}
          maxLength={128}
          required
        />
        <PasswordField
          id="confirm"
          name="confirm"
          label="Repeat it"
          autoComplete="new-password"
          minLength={8}
          maxLength={128}
          required
        />
        {error && (
          <Problem>
            {error}{" "}
            {error.includes("expired") && (
              <Link href="/forgot-password" className="underline underline-offset-4">
                Get a new link
              </Link>
            )}
          </Problem>
        )}
        <Button type="submit" size="lg" disabled={pending} className="mt-2 w-full">
          {pending && <LoaderCircle aria-hidden className="animate-spin" />}
          {pending ? "Saving…" : "Save and sign in"}
        </Button>
      </form>
    </Shell>
  );
}
