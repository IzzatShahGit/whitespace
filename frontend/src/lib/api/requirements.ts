"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { BRIEF_POLL_MS, unwrap } from "@/lib/api/queries";
import type { components } from "@/lib/api/schema";

export type RequirementsOut = components["schemas"]["RequirementsOut"];
export type Requirement = components["schemas"]["Requirement"];
export type RequirementSource = components["schemas"]["RequirementSource"];

const key = (hs6: string, market: string, exporter: string) =>
  ["requirements", hs6, market, exporter] as const;

/** What a shipment needs to enter `market`; polls while the research runs. */
export function useRequirements(hs6: string, market: string, exporter: string | undefined) {
  return useQuery({
    queryKey: key(hs6, market, exporter ?? ""),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/markets/{market}/requirements", {
          params: { path: { market }, query: { hs6, exporter: exporter! } },
        }),
      ),
    enabled: Boolean(exporter) && exporter !== market,
    refetchInterval: (query) => (query.state.data?.status === "pending" ? BRIEF_POLL_MS : false),
  });
}

export function useRequestRequirements(hs6: string, market: string, exporter: string | undefined) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/markets/{market}/requirements", {
          params: { path: { market }, query: { hs6, exporter: exporter! } },
        }),
      ),
    onSuccess: (out) => client.setQueryData(key(hs6, market, exporter ?? ""), out),
  });
}

/** Tick or untick one item. Updates the list at once; rolls back if the server says no. */
export function useTickRequirement(hs6: string, market: string, exporter: string | undefined) {
  const client = useQueryClient();
  const k = key(hs6, market, exporter ?? "");
  return useMutation({
    mutationKey: [...k, "tick"],
    mutationFn: async ({ item, done }: { item: string; done: boolean }) => {
      const params = { params: { path: { market, item }, query: { hs6 } } };
      const { response } = done
        ? await api.PUT("/api/v1/markets/{market}/requirements/done/{item}", params)
        : await api.DELETE("/api/v1/markets/{market}/requirements/done/{item}", params);
      if (!response.ok) throw new Error("Couldn’t save that. Please try again.");
    },
    onMutate: async ({ item, done }) => {
      await client.cancelQueries({ queryKey: k });
      const before = client.getQueryData<RequirementsOut>(k);
      if (before) {
        const rest = (before.done ?? []).filter((d) => d !== item);
        client.setQueryData<RequirementsOut>(k, { ...before, done: done ? [...rest, item] : rest });
      }
      return { before };
    },
    onError: (_error, _vars, context) => {
      if (context?.before) client.setQueryData(k, context.before);
    },
    // After the last of several quick ticks settles, re-read the server's truth.
    onSettled: () => {
      if (client.isMutating({ mutationKey: [...k, "tick"] }) <= 1) {
        void client.invalidateQueries({ queryKey: k });
      }
    },
  });
}
