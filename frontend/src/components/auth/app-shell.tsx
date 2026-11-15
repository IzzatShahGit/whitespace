"use client";

import { useRouter } from "next/navigation";
import { type CSSProperties, useEffect, useState } from "react";

import { Logo } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";
import { currentUser, signOut, type User } from "@/lib/auth";

// Signed-in area. Loads the user; if the session is gone, goes back to sign-in.
export function AppShell() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>();

  useEffect(() => {
    currentUser().then((u) => {
      if (u) setUser(u);
      else router.replace("/login?next=/app");
    });
  }, [router]);

  async function onSignOut() {
    await signOut();
    router.replace("/");
    router.refresh();
  }

  if (!user) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-sage">Loading…</div>
    );
  }

  const firstName = user.full_name.split(" ")[0];
  return (
    <>
      <header className="border-b border-ink-line/60">
        <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <Logo href="/app" />
          <div className="flex items-center gap-4">
            <span className="hidden text-sm text-sage sm:block">{user.email}</span>
            <Button variant="secondary" className="h-9 px-4" onClick={onSignOut}>
              Sign out
            </Button>
          </div>
        </nav>
      </header>

      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-10 px-6 py-14">
        <div className="rise-in">
          <h1 className="text-3xl font-semibold tracking-tight">Hi {firstName},</h1>
          <p className="mt-2 text-sage">What do you want to export?</p>
        </div>

        <div
          className="rise-in flex flex-col gap-3 sm:flex-row"
          style={{ "--delay": "120ms" } as CSSProperties}
        >
          <input
            disabled
            placeholder="e.g. cotton bed sheets"
            className="h-12 flex-1 rounded-xl border border-ink-line bg-ink-raised px-4 text-cream placeholder:text-sage-dim/60"
          />
          <Button disabled className="h-12">
            Find markets
          </Button>
        </div>
        <p className="-mt-6 text-xs text-sage-dim">
          Market search goes live once the trade data pipeline lands.
        </p>
      </main>
    </>
  );
}
