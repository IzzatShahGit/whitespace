"use client";

import { CircleAlert, LoaderCircle, MailCheck, MailX } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { type ReactNode, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";

function Shell({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <div className="rise-in w-full max-w-sm">
      <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-soft text-brand [&>svg]:h-5 [&>svg]:w-5">
        {icon}
      </span>
      <h1 className="mt-5 text-2xl font-semibold tracking-tight">{title}</h1>
      <div className="mt-3 text-muted">{children}</div>
    </div>
  );
}

/** From the confirmation email: POSTs the token once (link scanners only GET the page). */
export function VerifyEmail() {
  const token = useSearchParams().get("token") ?? "";
  const [state, setState] = useState<"working" | "done" | "failed">(
    token.length < 20 ? "failed" : "working",
  );
  const sent = useRef(false);

  useEffect(() => {
    if (sent.current || token.length < 20) return; // effects may run twice in development
    sent.current = true;
    void api
      .POST("/api/v1/auth/verify-email", { body: { token } })
      .then(({ response }) => setState(response.ok ? "done" : "failed"));
  }, [token]);

  if (state === "working") {
    return (
      <Shell icon={<LoaderCircle className="animate-spin" />} title="Confirming…">
        One moment.
      </Shell>
    );
  }
  if (state === "failed") {
    return (
      <Shell icon={<CircleAlert />} title="This link has expired">
        <p>
          It may have been used already. Turn the weekly email on again in Settings for a new link.
        </p>
        <Link
          href="/app/settings"
          className="mt-4 inline-block font-medium text-brand hover:underline"
        >
          Open Settings
        </Link>
      </Shell>
    );
  }
  return (
    <Shell icon={<MailCheck />} title="Email confirmed">
      <p>Your weekly email is on. It arrives on Monday mornings when there’s something new.</p>
      <Link href="/app" className="mt-4 inline-block font-medium text-brand hover:underline">
        Go to Whitespace
      </Link>
    </Shell>
  );
}

/** From the link in the weekly email: one press stops it, no sign-in needed. */
export function Unsubscribe() {
  const search = useSearchParams();
  const u = search.get("u") ?? "";
  const t = search.get("t") ?? "";
  const [state, setState] = useState<"ask" | "working" | "done" | "failed">("ask");

  async function stop() {
    setState("working");
    const { response } = await api.POST("/api/v1/auth/unsubscribe", { body: { u, t } });
    setState(response.ok ? "done" : "failed");
  }

  if (state === "done") {
    return (
      <Shell icon={<MailX />} title="You’re unsubscribed">
        <p>No more weekly emails. You can turn them back on in Settings any time.</p>
      </Shell>
    );
  }
  if (state === "failed") {
    return (
      <Shell icon={<CircleAlert />} title="That link didn’t work">
        <p>Sign in and turn the weekly email off in Settings instead.</p>
        <Link
          href="/app/settings"
          className="mt-4 inline-block font-medium text-brand hover:underline"
        >
          Open Settings
        </Link>
      </Shell>
    );
  }
  return (
    <Shell icon={<MailX />} title="Stop the weekly email?">
      <p>You’ll keep your account and pipeline; we just won’t email you each week.</p>
      <Button
        className="mt-5 w-full"
        size="lg"
        disabled={state === "working"}
        onClick={() => void stop()}
      >
        {state === "working" && <LoaderCircle className="animate-spin" />} Unsubscribe
      </Button>
    </Shell>
  );
}
