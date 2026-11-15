"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { Logo } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";
import type { User } from "@/lib/api/queries";
import { signOut } from "@/lib/auth";

const NAV = [
  { href: "/app", label: "Dashboard" },
  { href: "/app/browse", label: "Browse" },
  { href: "/onboarding", label: "Preferences" },
];

// Dashboard owns /app and the market pages; Browse owns /app/browse.
const isDashboard = (path: string) => path.startsWith("/app") && !path.startsWith("/app/browse");

export function AppHeader({ user }: { user: User }) {
  const router = useRouter();
  const pathname = usePathname();
  const client = useQueryClient();

  async function onSignOut() {
    await signOut();
    client.clear(); // nothing from this user's session survives sign-out
    router.replace("/");
    router.refresh();
  }

  return (
    <header className="sticky top-0 z-20 border-b border-ink-line/60 bg-ink/85 backdrop-blur-md">
      <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-6">
        <div className="flex items-center gap-6">
          <Logo href="/app" />
          <div className="hidden items-center gap-1 sm:flex">
            {NAV.map(({ href, label }) => {
              const active = href === "/app" ? isDashboard(pathname) : pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={`rounded-full px-3 py-1.5 text-sm transition-colors ${
                    active ? "bg-ink-raised text-cream" : "text-sage hover:text-cream"
                  }`}
                >
                  {label}
                </Link>
              );
            })}
          </div>
        </div>
        <div className="flex items-center gap-4">
          <span className="hidden text-sm text-sage md:block">{user.email}</span>
          <Button variant="secondary" className="h-9 px-4" onClick={onSignOut}>
            Sign out
          </Button>
        </div>
      </nav>
    </header>
  );
}
