import type { Metadata } from "next";

import { WatchlistView } from "@/components/watch/watchlist-view";

// Renders after the session check: see (signed-in)/layout.tsx.
export const instant = false;

export const metadata: Metadata = { title: "Watchlist · Whitespace" };

export default function WatchlistPage() {
  return <WatchlistView />;
}
