"use client";

// Watchlist and alerts: follow (product, market) pairs; notifications when monthly data moves.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { unwrap } from "@/lib/api/queries";
import type { components } from "@/lib/api/schema";

export type Watch = components["schemas"]["WatchOut"];
export type Notification = components["schemas"]["NotificationOut"];

const watchKeys = {
  all: ["watches"] as const,
  status: (exporter: string, hs6: string, market: string) =>
    ["watches", "status", exporter, hs6, market] as const,
  notifications: ["notifications"] as const,
};

const NOTIFICATIONS_POLL_MS = 60_000; // alerts arrive with monthly data: a minute is plenty

export function useWatches() {
  return useQuery({
    queryKey: watchKeys.all,
    queryFn: () => unwrap(api.GET("/api/v1/watches")),
  });
}

/** Whether this market is watched (for the toggle on market pages). */
export function useWatchStatus(exporter: string, hs6: string, market: string) {
  return useQuery({
    queryKey: watchKeys.status(exporter, hs6, market),
    queryFn: () =>
      unwrap(api.GET("/api/v1/watches/check", { params: { query: { exporter, hs6, market } } })),
  });
}

export function useToggleWatch(exporter: string, hs6: string, market: string) {
  const client = useQueryClient();
  const statusKey = watchKeys.status(exporter, hs6, market);
  return useMutation({
    mutationFn: async (current: { watching: boolean; id: string | null }) => {
      if (current.watching && current.id) {
        const { response } = await api.DELETE("/api/v1/watches/{watch_id}", {
          params: { path: { watch_id: current.id } },
        });
        if (!response.ok && response.status !== 404) throw new Error("Couldn’t stop watching");
        return { watching: false, id: null };
      }
      const watch = await unwrap(api.POST("/api/v1/watches", { body: { exporter, hs6, market } }));
      return { watching: true, id: watch.id };
    },
    onSuccess: (status) => {
      client.setQueryData(statusKey, status);
      void client.invalidateQueries({ queryKey: watchKeys.all, exact: true });
    },
  });
}

export function useRemoveWatch() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { response } = await api.DELETE("/api/v1/watches/{watch_id}", {
        params: { path: { watch_id: id } },
      });
      if (!response.ok && response.status !== 404) throw new Error("Couldn’t remove it");
    },
    onSuccess: () => void client.invalidateQueries({ queryKey: watchKeys.all }),
  });
}

export function useNotifications(limit = 20) {
  return useQuery({
    queryKey: [...watchKeys.notifications, limit],
    queryFn: () => unwrap(api.GET("/api/v1/notifications", { params: { query: { limit } } })),
    refetchInterval: NOTIFICATIONS_POLL_MS,
  });
}

export function useMarkRead() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (which: { ids: string[] } | { all: true }) =>
      unwrap(
        api.POST("/api/v1/notifications/read", {
          body: "all" in which ? { all: true } : { ids: which.ids, all: false },
        }),
      ),
    onSuccess: () => void client.invalidateQueries({ queryKey: watchKeys.notifications }),
  });
}
