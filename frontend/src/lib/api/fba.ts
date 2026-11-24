"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { unwrap } from "@/lib/api/queries";
import type { components } from "@/lib/api/schema";

export type FbaInput = components["schemas"]["FbaInput"];
export type FbaEstimate = components["schemas"]["FbaEstimate"];
export type FbaOptions = components["schemas"]["FbaOptions"];
export type FbaCategoryKey = FbaInput["category"];
export type FbaCostItem = components["schemas"]["FbaCost"];

const DAY = 24 * 60 * 60 * 1000;

/** Amazon categories and the countries we can ship from (public, cached a day). */
export function useFbaOptions() {
  return useQuery({
    queryKey: ["fba", "options"],
    queryFn: () => unwrap(api.GET("/api/v1/public/fba/options")),
    staleTime: DAY,
  });
}

/**
 * Unit economics for one product on Amazon US. `signedOut` uses the rate-limited public
 * endpoint. The last result stays on screen while a changed input recalculates.
 */
export function useFbaEstimate(input: FbaInput | null, { signedOut = false } = {}) {
  return useQuery({
    queryKey: ["fba", "estimate", signedOut, input],
    queryFn: () =>
      unwrap(
        signedOut
          ? api.POST("/api/v1/public/fba/estimate", { body: input! })
          : api.POST("/api/v1/fba/estimate", { body: input! }),
      ),
    enabled: input !== null,
    placeholderData: keepPreviousData,
    staleTime: 10 * 60 * 1000,
    retry: false,
  });
}
