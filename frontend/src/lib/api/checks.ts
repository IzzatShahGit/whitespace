"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { Contact } from "@/lib/api/pipeline";
import { unwrap } from "@/lib/api/queries";
import type { components } from "@/lib/api/schema";

export type BuyerCheck = components["schemas"]["BuyerCheckOut"];
export type CheckIn = components["schemas"]["CheckIn"];
export type Finding = components["schemas"]["Finding"];

const latestKey = (id: string) => ["buyer-checks", "contact", id] as const;

/** Run a check; for a pipeline contact the card's verdict updates too. */
export function useBuyerCheck() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: CheckIn) => unwrap(api.POST("/api/v1/buyer-checks", { body })),
    onSuccess: (out) => {
      if (!out.contact_id) return;
      client.setQueryData(latestKey(out.contact_id), out);
      client.setQueryData<Contact[]>(["pipeline"], (list) =>
        list?.map((c) => (c.id === out.contact_id ? { ...c, check_verdict: out.verdict } : c)),
      );
      void client.invalidateQueries({ queryKey: ["pipeline", "events", out.contact_id] });
    },
  });
}

/** The last check of a pipeline contact (only asked for when the card says there is one). */
export function useLatestCheck(id: string, enabled: boolean) {
  return useQuery({
    queryKey: latestKey(id),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/buyer-checks/contacts/{contact_id}", {
          params: { path: { contact_id: id } },
        }),
      ),
    enabled,
  });
}
