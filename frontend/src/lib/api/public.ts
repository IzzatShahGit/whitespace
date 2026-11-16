"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { unwrap } from "@/lib/api/queries";
import type { components } from "@/lib/api/schema";

// Signed-out data for the landing page (rate-limited per visitor, cacheable).

export type Preview = components["schemas"]["Preview"];
export type PreviewMarket = components["schemas"]["PreviewMarket"];

/** The top 3 markets for a product typed in plain words, from one country. 404: no match. */
export function usePreview(exporter: string, q: string) {
  const query = q.trim();
  return useQuery({
    queryKey: ["public", "preview", exporter, query.toLowerCase()],
    queryFn: () =>
      unwrap(api.GET("/api/v1/public/preview", { params: { query: { exporter, q: query } } })),
    enabled: query.length >= 2,
    staleTime: 60 * 60 * 1000, // the server caches it for an hour too
    retry: false,
  });
}
