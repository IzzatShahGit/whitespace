"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { Logo } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";
import type { User } from "@/lib/api/queries";
import { signOut } from "@/lib/auth";

const NAV = [
  { href: "/app", label: "Sell" },
  { href: "/app/buy", label: "Buy" },
  { href: "/app/ask", label: "Ask" },
  { href: "/app/browse", label: "Browse" },
  { href: "/onboarding", label: "Preferences" },
];

// "Sell" owns /app and the market pages; the other sections own their prefixes.
function isActive(href: string, path: string): boolean {
  if (href !== "/app") return path.startsWith(href);
  return path.startsWith("/app") && !NAV.some((n) => n.href !== "/app" && path.startsWith(n.href));
}

function NavLinks({ pathname }: { pathname: string }) {
  return NAV.map(({ href, label }) => {
    const active = isActive(href, pathname);
    return (
      <Link
        key={href}
        href={href}
        aria-current={active ? "page" : undefined}
        className={`shrink-0 rounded-full px-3 py-1.5 text-sm transition-colors ${
          active ? "bg-ink-raised text-cream" : "text-sage hover:text-cream"
        }`}
      >
        {label}
      </Link>
    );
  });
}

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
            <NavLinks pathname={pathname} />
          </div>
        </div>
        <div className="flex items-center gap-4">
          <span className="hidden text-sm text-sage md:block">{user.email}</span>
          <Button variant="secondary" className="h-9 px-4" onClick={onSignOut}>
            Sign out
          </Button>
        </div>
      </nav>
      {/* Phones: the same sections as a scrollable tab strip under the bar. */}
      <div className="flex gap-1 overflow-x-auto border-t border-ink-line/60 px-4 py-2 sm:hidden">
        <NavLinks pathname={pathname} />
      </div>
    </header>
  );
}
