"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { unwrap } from "@/lib/api/queries";
import type { components } from "@/lib/api/schema";

export type Ideas = components["schemas"]["IdeasOut"];
export type AmazonCategory = components["schemas"]["AmazonCategoryOut"];
export type BestsellerItem = components["schemas"]["BestsellerItem"];
export type CategoryTrend = components["schemas"]["CategoryTrend"];
export type RisingProduct = components["schemas"]["RisingProduct"];

/** Amazon best sellers (weekly) and rising US imports (monthly). Public; the API caches
 * it for 15 minutes, and so do we. */
export function useIdeas() {
  return useQuery({
    queryKey: ["ideas"],
    queryFn: () => unwrap(api.GET("/api/v1/public/ideas")),
    staleTime: 15 * 60 * 1000,
  });
}
