import type { Metadata } from "next";

import { WatchlistView } from "@/components/watch/watchlist-view";

export const metadata: Metadata = { title: "Watchlist · Whitespace" };

export default function WatchlistPage() {
  return <WatchlistView />;
}
