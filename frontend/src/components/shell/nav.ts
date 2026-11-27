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
  Lightbulb,
  PackageSearch,
  Settings,
  ShoppingCart,
  Ship,
  ShieldCheck,
  Sparkles,
  TrendingUp,
} from "lucide-react";

export type NavId =
  | "home"
  | "sell"
  | "buy"
  | "amazon"
  | "ideas"
  | "ask"
  | "pipeline"
  | "check"
  | "quotes"
  | "shipments"
  | "tenders"
  | "watchlist"
  | "explore"
  | "learn"
  | "settings"
  | "usage";

export type NavItem = {
  id: NavId; // its words come from the i18n messages: nav.<id> and nav.<id>Hint
  href: string;
  label: string; // English, for search matching
  icon: LucideIcon;
  hint: string; // shown in search and tooltips
};

/** Every section, in one place: the sidebar, phone tabs and ⌘K search all read this. */
export const NAV: NavItem[] = [
  { id: "home", href: "/app", label: "Home", icon: Home, hint: "Your overview" },
  { id: "sell", href: "/app/markets", label: "Sell", icon: TrendingUp, hint: "Where to sell" },
  { id: "buy", href: "/app/buy", label: "Buy", icon: PackageSearch, hint: "Where to buy" },
  {
    id: "ideas",
    href: "/app/ideas",
    label: "Product ideas",
    icon: Lightbulb,
    hint: "Amazon best sellers and rising US imports",
  },
  {
    id: "amazon",
    href: "/app/fba",
    label: "Sell on Amazon",
    icon: ShoppingCart,
    hint: "Profit per unit on Amazon US: freight, duty, fees",
  },
  { id: "ask", href: "/app/ask", label: "Ask", icon: Sparkles, hint: "Ask the AI guide" },
  {
    id: "pipeline",
    href: "/app/pipeline",
    label: "Pipeline",
    icon: KanbanSquare,
    hint: "Companies you're contacting",
  },
  {
    id: "check",
    href: "/app/check",
    label: "Check a buyer",
    icon: ShieldCheck,
    hint: "Is this buyer real? Sanctions, registers, scam signs",
  },
  {
    id: "quotes",
    href: "/app/quotes",
    label: "Quotes",
    icon: FileText,
    hint: "Quotes and proforma invoices",
  },
  {
    id: "shipments",
    href: "/app/shipments",
    label: "Shipments",
    icon: Ship,
    hint: "Invoices, packing lists and origin papers",
  },
  {
    id: "tenders",
    href: "/app/tenders",
    label: "Tenders",
    icon: Gavel,
    hint: "Public buyers asking for your products",
  },
  {
    id: "watchlist",
    href: "/app/watchlist",
    label: "Watchlist",
    icon: Bell,
    hint: "Markets you follow",
  },
  { id: "explore", href: "/app/browse", label: "Explore", icon: Compass, hint: "Browse niches" },
];

/** How the sidebar groups NAV: a few top items, then two named sections. */
export const NAV_GROUPS: { heading: "groupFind" | "groupDeals" | null; ids: NavId[] }[] = [
  { heading: null, ids: ["home", "ask"] },
  { heading: "groupFind", ids: ["sell", "buy", "ideas", "amazon", "explore", "watchlist"] },
  { heading: "groupDeals", ids: ["pipeline", "check", "quotes", "shipments", "tenders"] },
];

export const LEARN: NavItem = {
  id: "learn",
  href: "/app/learn",
  label: "Trade terms",
  icon: BookOpen,
  hint: "Duty, FOB, HS code… in plain words",
};

export const SETTINGS: NavItem = {
  id: "settings",
  href: "/app/settings",
  label: "Settings",
  icon: Settings,
  hint: "Profile, business and appearance",
};

/** Admins only: shown when /auth/me says is_admin (the API also refuses everyone else). */
export const USAGE: NavItem = {
  id: "usage",
  href: "/app/admin",
  label: "Users & visitors",
  icon: BarChart3,
  hint: "Users, visitors, sign-ups and feature use",
};

/** The section a path belongs to ("/app/markets/630260/DEU" -> Sell). */
export function activeHref(path: string): string | undefined {
  const match = [...NAV, LEARN, SETTINGS, USAGE]
    .filter((item) => item.href !== "/app" && path.startsWith(item.href))
    .sort((a, b) => b.href.length - a.href.length)[0];
  return match?.href ?? (path === "/app" ? "/app" : undefined);
}
