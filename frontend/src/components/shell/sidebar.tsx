"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Logo } from "@/components/brand/logo";
import {
  activeHref,
  LEARN,
  NAV,
  NAV_GROUPS,
  type NavItem,
  SETTINGS,
  USAGE,
} from "@/components/shell/nav";
import { useChatSuggestions, useMe } from "@/lib/api/queries";
import { useT } from "@/lib/i18n";

function UsageMeter() {
  const t = useT();
  const usage = useChatSuggestions();
  if (!usage.data) return null;
  return (
    <Link href="/app/ask" className="px-3 py-1 text-xs text-subtle transition-colors hover:text-fg">
      {t("shell.aiLeft", { count: usage.data.remaining_today })}
    </Link>
  );
}

const itemClass = (active: boolean) =>
  `group flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition-colors duration-150 ${
    active
      ? "bg-brand-soft font-medium text-brand-strong"
      : "text-muted hover:bg-surface-2 hover:text-fg"
  }`;

function NavLink({ item, active }: { item: NavItem; active: boolean }) {
  const t = useT();
  const Icon = item.icon;
  return (
    <Link href={item.href} aria-current={active ? "page" : undefined} className={itemClass(active)}>
      <Icon
        className={`h-[18px] w-[18px] transition-colors ${active ? "text-brand" : "text-subtle group-hover:text-fg"}`}
        strokeWidth={1.8}
      />
      {t(`nav.${item.id}`)}
      {item.id === "ask" && (
        <span className="ml-auto rounded-full bg-accent-soft px-1.5 py-0.5 text-xs font-semibold text-accent-strong">
          AI
        </span>
      )}
      {item.id === "usage" && (
        <span className="ml-auto rounded-full bg-surface-2 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-subtle uppercase">
          {t("nav.admin")}
        </span>
      )}
    </Link>
  );
}

/** Desktop navigation: always visible, grouped by job, the current section highlighted. */
export function Sidebar() {
  const t = useT();
  const current = activeHref(usePathname());
  const isAdmin = useMe().data?.is_admin === true;
  const byId = new Map(NAV.map((item) => [item.id, item]));
  return (
    <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col overflow-y-auto border-r border-line bg-canvas px-3 py-4 lg:flex">
      <div className="px-2 pb-5">
        <Logo href="/app" />
      </div>
      <nav aria-label="Main" className="flex flex-1 flex-col gap-4">
        {NAV_GROUPS.map((group) => (
          <div key={group.heading ?? "top"} className="flex flex-col gap-0.5">
            {group.heading && (
              <p className="px-3 pb-1 text-[11px] font-semibold tracking-wider text-subtle uppercase">
                {t(`nav.${group.heading}`)}
              </p>
            )}
            {group.ids.map((id) => {
              const item = byId.get(id);
              return item ? <NavLink key={id} item={item} active={current === item.href} /> : null;
            })}
          </div>
        ))}
      </nav>
      <div className="flex flex-col gap-0.5 border-t border-line pt-3">
        <UsageMeter />
        {isAdmin && <NavLink item={USAGE} active={current === USAGE.href} />}
        <NavLink item={LEARN} active={current === LEARN.href} />
        <NavLink item={SETTINGS} active={current === SETTINGS.href} />
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
