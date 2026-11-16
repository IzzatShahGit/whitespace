"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { unwrap } from "@/lib/api/queries";
import type { components } from "@/lib/api/schema";

export type RangeIdea = components["schemas"]["RangeIdea"];

/** Products the user could add next (same customs family, strong markets). */
export function useGrowRange(enabled: boolean) {
  return useQuery({
    queryKey: ["grow"],
    queryFn: () => unwrap(api.GET("/api/v1/me/grow")),
    enabled,
    staleTime: 10 * 60 * 1000,
  });
}
