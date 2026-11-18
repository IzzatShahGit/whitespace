"use client";

import { CircleAlert, LoaderCircle } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";

import { GoogleButton } from "@/components/auth/google-button";
import { PasswordField } from "@/components/auth/password-field";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { providers, signIn, signUp } from "@/lib/auth";

type Mode = "login" | "signup";

const copy: Record<Mode, { title: string; subtitle: string; submit: string; pending: string }> = {
  login: {
    title: "Welcome back",
    subtitle: "Sign in to see your markets.",
    submit: "Sign in",
    pending: "Signing in…",
  },
  signup: {
    title: "Create your free account",
    subtitle: "Free to start. No card needed.",
    submit: "Create account",
    pending: "Creating your account…",
  },
};

// Only same-site paths, so `?next=` can't send users to another website.
function safeNext(value: string | null): string {
  return value?.startsWith("/") && !value.startsWith("//") && !value.startsWith("/\\")
    ? value
    : "/app";
}

const GOOGLE_ERROR = "Google sign-in didn't complete. Please try again.";

export function AuthForm({ mode }: { mode: Mode }) {
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  // The Google flow returns ?error=google on failure; the reason stays in server logs.
  const [error, setError] = useState(params.get("error") === "google" ? GOOGLE_ERROR : undefined);
  const [pending, setPending] = useState(false);
  const [canReset, setCanReset] = useState(false);

  useEffect(() => {
    if (mode === "login") void providers().then((p) => setCanReset(p.passwordReset));
  }, [mode]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(undefined);
    setPending(true);
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email"));
    const password = String(form.get("password"));
    const result =
      mode === "signup"
        ? await signUp({ email, password, full_name: String(form.get("full_name")) })
        : await signIn({ email, password });
    if (result.error) {
      setError(result.error);
      setPending(false);
      return;
    }
    router.replace(next);
    router.refresh();
  }

  const text = copy[mode];
  // Switching between sign-in and sign-up keeps where the visitor was heading.
  const carry = next === "/app" ? "" : `?next=${encodeURIComponent(next)}`;
  return (
    <div className="rise-in w-full max-w-sm">
      <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{text.title}</h1>
      <p className="mt-2 text-muted">{text.subtitle}</p>

      <div className="mt-8">
        <GoogleButton next={next} />
      </div>

      <form onSubmit={onSubmit} className="flex flex-col gap-4" aria-busy={pending}>
        {mode === "signup" && (
          <Field
            id="full_name"
            name="full_name"
            label="Your name"
            autoComplete="name"
            required
            maxLength={120}
          />
        )}
        <Field
          id="email"
          name="email"
          type="email"
          label="Email"
          autoComplete="email"
          inputMode="email"
          required
        />
        <PasswordField
          id="password"
          name="password"
          label="Password"
          autoComplete={mode === "signup" ? "new-password" : "current-password"}
          hint={mode === "signup" ? "At least 8 characters." : undefined}
          minLength={mode === "signup" ? 8 : undefined}
          maxLength={128}
          required
        />
        {canReset && (
          <Link
            href="/forgot-password"
            className="-mt-2 self-end text-sm text-muted underline-offset-4 hover:text-fg hover:underline"
          >
            Forgot your password?
          </Link>
        )}

        {error && (
          <div
            role="alert"
            className="flex items-start gap-2.5 rounded-xl bg-negative-soft px-3.5 py-3 text-sm leading-5 text-negative"
          >
            <CircleAlert aria-hidden className="mt-px h-4 w-4 shrink-0" />
            {error}
          </div>
        )}

        <Button type="submit" size="lg" disabled={pending} className="mt-2 w-full">
          {pending && <LoaderCircle aria-hidden className="animate-spin" />}
          {pending ? text.pending : text.submit}
        </Button>
        {mode === "signup" && (
          <p className="text-center text-xs leading-5 text-subtle">
            By creating an account you agree to our{" "}
            <Link href="/terms" className="underline underline-offset-2 hover:text-fg">
              Terms
            </Link>{" "}
            and{" "}
            <Link href="/privacy" className="underline underline-offset-2 hover:text-fg">
              Privacy policy
            </Link>
            .
          </p>
        )}
      </form>

      <p className="mt-8 text-center text-sm text-muted">
        {mode === "login" ? (
          <>
            New to Whitespace?{" "}
            <Link
              href={`/signup${carry}`}
              className="font-medium text-brand underline-offset-4 hover:underline"
            >
              Create a free account
            </Link>
          </>
        ) : (
          <>
            Already have an account?{" "}
            <Link
              href={`/login${carry}`}
              className="font-medium text-brand underline-offset-4 hover:underline"
            >
              Sign in
            </Link>
          </>
        )}
      </p>
    </div>
  );
}
