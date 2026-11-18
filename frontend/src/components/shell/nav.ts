import {
  BarChart3,
  Bell,
  BookOpen,
  Compass,
  FileText,
  Gavel,
  Home,
  KanbanSquare,
  type LucideIcon,
  PackageSearch,
  Settings,
  Sparkles,
  TrendingUp,
} from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  hint: string; // shown in search and tooltips
};

/** Every section, in one place: the sidebar, phone tabs and ⌘K search all read this. */
export const NAV: NavItem[] = [
  { href: "/app", label: "Home", icon: Home, hint: "Your overview" },
  { href: "/app/markets", label: "Sell", icon: TrendingUp, hint: "Where to sell" },
  { href: "/app/buy", label: "Buy", icon: PackageSearch, hint: "Where to buy" },
  { href: "/app/ask", label: "Ask", icon: Sparkles, hint: "Ask the AI guide" },
  {
    href: "/app/pipeline",
    label: "Pipeline",
    icon: KanbanSquare,
    hint: "Companies you're contacting",
  },
  { href: "/app/quotes", label: "Quotes", icon: FileText, hint: "Quotes and proforma invoices" },
  {
    href: "/app/tenders",
    label: "Tenders",
    icon: Gavel,
    hint: "Public buyers asking for your products",
  },
  { href: "/app/watchlist", label: "Watchlist", icon: Bell, hint: "Markets you follow" },
  { href: "/app/browse", label: "Explore", icon: Compass, hint: "Browse niches" },
];

export const LEARN: NavItem = {
  href: "/app/learn",
  label: "Trade terms",
  icon: BookOpen,
  hint: "Duty, FOB, HS code… in plain words",
};

export const SETTINGS: NavItem = {
  href: "/app/settings",
  label: "Settings",
  icon: Settings,
  hint: "Profile, business and appearance",
};

/** Admins only: shown when /auth/me says is_admin (the API also refuses everyone else). */
export const USAGE: NavItem = {
  href: "/app/admin",
  label: "Usage",
  icon: BarChart3,
  hint: "Visitors, sign-ups and feature use",
};

/** The section a path belongs to ("/app/markets/630260/DEU" -> Sell). */
export function activeHref(path: string): string | undefined {
  const match = [...NAV, LEARN, SETTINGS, USAGE]
    .filter((item) => item.href !== "/app" && path.startsWith(item.href))
    .sort((a, b) => b.href.length - a.href.length)[0];
  return match?.href ?? (path === "/app" ? "/app" : undefined);
}
