"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  BarChart3,
  LogOut,
  Monitor,
  Moon,
  Search,
  SlidersHorizontal,
  Sun,
  UserRound,
} from "lucide-react";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";

import { Logo } from "@/components/brand/logo";
import { openSearch } from "@/components/shell/command-palette";
import { MenuItem, Popover } from "@/components/ui/menu";
import type { User } from "@/lib/api/queries";
import { signOut } from "@/lib/auth";
import { useT } from "@/lib/i18n";
import type { MessageKey } from "@/lib/i18n/en";
import { type ThemeChoice, useTheme } from "@/lib/theme";

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return (
    ((parts[0]?.[0] ?? "") + (parts.length > 1 ? (parts.at(-1)?.[0] ?? "") : "")).toUpperCase() ||
    "?"
  );
}

export function Avatar({ name, size = "h-9 w-9 text-sm" }: { name: string; size?: string }) {
  return (
    <span
      aria-hidden
      className={`flex ${size} items-center justify-center rounded-full bg-gradient-to-br from-brand to-brand-strong font-semibold text-on-brand shadow-card`}
    >
      {initials(name)}
    </span>
  );
}

const THEMES: { value: ThemeChoice; label: MessageKey; icon: ReactNode }[] = [
  { value: "light", label: "shell.themeLight", icon: <Sun className="h-4 w-4" /> },
  { value: "dark", label: "shell.themeDark", icon: <Moon className="h-4 w-4" /> },
  { value: "system", label: "shell.themeAuto", icon: <Monitor className="h-4 w-4" /> },
];

export function ThemeSwitch() {
  const t = useT();
  const [theme, setTheme] = useTheme();
  return (
    <div
      role="radiogroup"
      aria-label="Theme"
      className="grid grid-cols-3 gap-1 rounded-xl bg-canvas p-1"
    >
      {THEMES.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={theme === option.value}
          onClick={() => setTheme(option.value)}
          className={`flex items-center justify-center gap-1.5 rounded-lg py-1.5 text-xs transition-all ${
            theme === option.value ? "bg-surface text-fg shadow-card" : "text-muted hover:text-fg"
          }`}
        >
          {option.icon}
          {t(option.label)}
        </button>
      ))}
    </div>
  );
}

function ProfileMenu({ user }: { user: User }) {
  const t = useT();
  const router = useRouter();
  const client = useQueryClient();

  async function onSignOut() {
    await signOut();
    client.clear(); // nothing from this user's session survives sign-out
    router.replace("/");
    router.refresh();
  }

  return (
    <Popover
      label={t("shell.accountMenu")}
      button={() => <Avatar name={user.full_name} />}
      width="w-72"
    >
      {(close) => (
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-3 px-3 py-2.5">
            <Avatar name={user.full_name} size="h-10 w-10 text-sm" />
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{user.full_name}</p>
              <p className="truncate text-xs text-muted">{user.email}</p>
            </div>
          </div>
          <div className="my-1 h-px bg-line" />
          <MenuItem icon={<UserRound />} href="/app/settings" onClick={close}>
            {t("shell.profileAccount")}
          </MenuItem>
          <MenuItem icon={<SlidersHorizontal />} href="/app/settings/business" onClick={close}>
            {t("shell.businessPrefs")}
          </MenuItem>
          {user.is_admin && (
            <MenuItem icon={<BarChart3 />} href="/app/admin" onClick={close}>
              {t("shell.usageAdmin")}
            </MenuItem>
          )}
          <div className="px-2 py-2">
            <p className="mb-1.5 px-1 text-xs font-medium tracking-wide text-subtle uppercase">
              {t("shell.appearance")}
            </p>
            <ThemeSwitch />
          </div>
          <div className="my-1 h-px bg-line" />
          <MenuItem icon={<LogOut />} onClick={onSignOut} danger>
            {t("shell.signOut")}
          </MenuItem>
        </div>
      )}
    </Popover>
  );
}

/** Search on the left, notifications and the account menu on the right. */
export function Topbar({ user, actions }: { user: User; actions?: ReactNode }) {
  const t = useT();
  return (
    <header className="sticky top-0 z-20 border-b border-line/70 bg-canvas/80 backdrop-blur-xl">
      <div className="flex h-16 items-center gap-3 px-4 sm:px-6">
        <div className="lg:hidden">
          <Logo href="/app" />
        </div>
        <button
          type="button"
          onClick={openSearch}
          className="ml-auto flex h-10 items-center gap-2 rounded-full border border-line bg-surface px-3 text-sm text-subtle shadow-card transition-colors hover:border-brand/40 hover:text-muted sm:w-80 lg:ml-0"
          aria-label="Search"
        >
          <Search className="h-4 w-4" />
          <span className="hidden flex-1 text-start sm:block">{t("shell.search")}</span>
          <kbd className="hidden rounded-md border border-line px-1.5 text-xs sm:block">⌘K</kbd>
        </button>
        <div className="flex items-center gap-2 sm:ml-auto">
          {actions}
          <ProfileMenu user={user} />
        </div>
      </div>
    </header>
  );
}
