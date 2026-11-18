"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Logo } from "@/components/brand/logo";
import { activeHref, LEARN, NAV, SETTINGS, USAGE } from "@/components/shell/nav";
import { useChatSuggestions, useMe } from "@/lib/api/queries";
import { useT } from "@/lib/i18n";

function UsageMeter() {
  const t = useT();
  const usage = useChatSuggestions();
  if (!usage.data) return null;
  return (
    <Link
      href="/app/ask"
      className="block rounded-2xl border border-line bg-surface p-3 text-xs text-muted transition-colors hover:border-brand/40"
    >
      {t("shell.aiLeft", { count: usage.data.remaining_today })}
    </Link>
  );
}

/** Desktop navigation: always visible, icons + words, the current section highlighted. */
export function Sidebar() {
  const t = useT();
  const current = activeHref(usePathname());
  const isAdmin = useMe().data?.is_admin === true;
  return (
    <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col border-r border-line bg-canvas px-3 py-4 lg:flex">
      <div className="px-2 pb-6">
        <Logo href="/app" />
      </div>
      <nav aria-label="Main" className="flex flex-1 flex-col gap-0.5">
        {NAV.map(({ id, href, icon: Icon }) => {
          const active = current === href;
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={`group flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition-all duration-200 ${
                active
                  ? "bg-surface font-medium text-fg shadow-card"
                  : "text-muted hover:bg-surface/70 hover:text-fg"
              }`}
            >
              <Icon
                className={`h-[18px] w-[18px] transition-colors ${active ? "text-brand" : "text-subtle group-hover:text-fg"}`}
                strokeWidth={1.8}
              />
              {t(`nav.${id}`)}
              {href === "/app/ask" && (
                <span className="ml-auto rounded-full bg-accent/15 px-1.5 py-0.5 text-xs font-semibold text-accent">
                  AI
                </span>
              )}
            </Link>
          );
        })}
      </nav>
      <div className="flex flex-col gap-2">
        <UsageMeter />
        {isAdmin && (
          <Link
            href={USAGE.href}
            aria-current={current === USAGE.href ? "page" : undefined}
            className={`flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition-colors ${
              current === USAGE.href ? "bg-surface text-fg" : "text-muted hover:text-fg"
            }`}
          >
            <USAGE.icon className="h-[18px] w-[18px] text-subtle" strokeWidth={1.8} />
            {t("nav.usage")}
            <span className="ml-auto rounded-full bg-surface-2 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-subtle uppercase">
              {t("nav.admin")}
            </span>
          </Link>
        )}
        <Link
          href={LEARN.href}
          aria-current={current === LEARN.href ? "page" : undefined}
          className={`flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition-colors ${
            current === LEARN.href ? "bg-surface text-fg" : "text-muted hover:text-fg"
          }`}
        >
          <LEARN.icon className="h-[18px] w-[18px] text-subtle" strokeWidth={1.8} />
          {t("nav.learn")}
        </Link>
        <Link
          href={SETTINGS.href}
          aria-current={current === SETTINGS.href ? "page" : undefined}
          className={`flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition-colors ${
            current === SETTINGS.href ? "bg-surface text-fg" : "text-muted hover:text-fg"
          }`}
        >
          <SETTINGS.icon className="h-[18px] w-[18px] text-subtle" strokeWidth={1.8} />
          {t("nav.settings")}
        </Link>
      </div>
    </aside>
  );
}

const MOBILE_ORDER = ["/app", "/app/markets", "/app/ask", "/app/buy", "/app/watchlist"];

/** Phones: the main sections as a bottom tab bar (thumb reach), with Ask raised in the middle. */
export function MobileTabs() {
  const t = useT();
  const current = activeHref(usePathname());
  const items = MOBILE_ORDER.map((href) => NAV.find((n) => n.href === href)!);
  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden"
    >
      <ul className="grid grid-cols-5 items-end">
        {items.map(({ id, href, icon: Icon }) => {
          const active = current === href;
          const ask = href === "/app/ask";
          return (
            <li key={href} className="flex justify-center">
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={`flex min-h-14 flex-col items-center justify-center gap-0.5 px-2 text-xs transition-colors ${
                  active ? "text-brand" : "text-subtle"
                }`}
              >
                {ask ? (
                  <span className="-mt-6 flex h-12 w-12 items-center justify-center rounded-2xl bg-action text-white shadow-pop">
                    <Icon className="h-5 w-5" strokeWidth={2} />
                  </span>
                ) : (
                  <Icon className="h-5 w-5" strokeWidth={active ? 2.2 : 1.8} />
                )}
                {t(`nav.${id}`)}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
