"use client";

import { Bell, BellRing } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useToggleWatch, useWatchStatus } from "@/lib/api/watch";

/** Follow a market: alerts arrive when its monthly imports or shares move. */
export function WatchButton({
  exporter,
  hs6,
  market,
}: {
  exporter: string;
  hs6: string;
  market: string;
}) {
  const status = useWatchStatus(exporter, hs6, market);
  const toggle = useToggleWatch(exporter, hs6, market);
  const watching = status.data?.watching ?? false;

  return (
    <Button
      variant="secondary"
      aria-pressed={watching}
      disabled={status.isPending || toggle.isPending}
      title={toggle.error?.message}
      onClick={() => status.data && toggle.mutate(status.data)}
      className={watching ? "border-brand/40 text-brand" : ""}
    >
      {watching ? <BellRing /> : <Bell />}
      {watching ? "Watching" : "Watch"}
    </Button>
  );
}
