"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, useState } from "react";

import { GoogleButton } from "@/components/auth/google-button";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { signIn, signUp } from "@/lib/auth";

type Mode = "login" | "signup";

const copy: Record<Mode, { title: string; subtitle: string; submit: string }> = {
  login: { title: "Welcome back", subtitle: "Sign in to your markets.", submit: "Sign in" },
  signup: {
    title: "Create your account",
    subtitle: "Free. No card needed.",
    submit: "Create account",
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
  return (
    <div className="rise-in w-full max-w-sm rounded-2xl border border-ink-line bg-ink-raised p-8 shadow-[0_30px_60px_-30px_rgba(0,0,0,0.6)]">
      <h1 className="text-2xl font-semibold tracking-tight">{text.title}</h1>
      <p className="mt-1 text-sm text-sage">{text.subtitle}</p>

      <div className="mt-7">
        <GoogleButton next={next} />
      </div>

      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        {mode === "signup" && (
          <Field
            id="full_name"
            name="full_name"
            label="Full name"
            autoComplete="name"
            required
            maxLength={120}
          />
        )}
        <Field id="email" name="email" type="email" label="Email" autoComplete="email" required />
        <Field
          id="password"
          name="password"
          type="password"
          label="Password"
          autoComplete={mode === "signup" ? "new-password" : "current-password"}
          hint={mode === "signup" ? "At least 8 characters." : undefined}
          minLength={mode === "signup" ? 8 : undefined}
          maxLength={128}
          required
        />

        {error && (
          <p role="alert" className="rounded-lg bg-ember/10 px-3 py-2 text-sm text-ember">
            {error}
          </p>
        )}

        <Button type="submit" disabled={pending} className="mt-2 w-full">
          {pending ? "One moment…" : text.submit}
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-sage">
        {mode === "login" ? (
          <>
            New here?{" "}
            <Link href="/signup" className="text-cream underline-offset-4 hover:underline">
              Create an account
            </Link>
          </>
        ) : (
          <>
            Already have an account?{" "}
            <Link href="/login" className="text-cream underline-offset-4 hover:underline">
              Sign in
            </Link>
          </>
        )}
      </p>
    </div>
  );
}
