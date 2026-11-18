"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { ApiError, unwrap } from "@/lib/api/queries";
import type { components } from "@/lib/api/schema";

export type Contact = components["schemas"]["ContactOut"];
export type ContactIn = components["schemas"]["ContactIn"];
export type Stage = Contact["stage"];
export type PipelineSummary = components["schemas"]["PipelineSummary"];

export const STAGES: { value: Stage; label: string }[] = [
  { value: "to_contact", label: "To contact" },
  { value: "emailed", label: "Emailed" },
  { value: "replied", label: "Replied" },
  { value: "samples", label: "Samples sent" },
  { value: "negotiating", label: "Negotiating" },
  { value: "won", label: "Won" },
  { value: "lost", label: "Closed" },
];
export const stageLabel = (s: Stage) => STAGES.find((x) => x.value === s)?.label ?? s;

const LIST = ["pipeline"] as const;
const SUMMARY = ["pipeline", "summary"] as const;

/** Same rule as the server, roughly: for showing "Saved" on company cards. */
export const sameCompany = (a: string, b: string) =>
  a
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim() ===
  b
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();

export function usePipeline() {
  return useQuery({
    queryKey: LIST,
    queryFn: () => unwrap(api.GET("/api/v1/pipeline")),
    staleTime: 30_000,
  });
}

export function usePipelineSummary() {
  return useQuery({
    queryKey: SUMMARY,
    queryFn: () => unwrap(api.GET("/api/v1/pipeline/summary")),
    staleTime: 60_000,
  });
}

function useRefresh() {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: ["pipeline"] });
}

export function useAddContact() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: ContactIn) => unwrap(api.POST("/api/v1/pipeline", { body })),
    onSuccess: () => void refresh(),
  });
}

/** Edits carry the version the user saw; if someone changed it meanwhile (409), the
 * list reloads and the error says so, instead of overwriting their change. */
export function useUpdateContact() {
  const client = useQueryClient();
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ id, ...body }: components["schemas"]["ContactPatch"] & { id: string }) =>
      unwrap(
        api.PATCH("/api/v1/pipeline/{contact_id}", { params: { path: { contact_id: id } }, body }),
      ),
    onSuccess: (updated) => {
      client.setQueryData<Contact[]>(LIST, (list) =>
        list?.map((c) => (c.id === updated.id ? updated : c)),
      );
      void client.invalidateQueries({ queryKey: SUMMARY });
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) void refresh();
    },
  });
}

export function useRemoveContact() {
  const client = useQueryClient();
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (id: string) => {
      const { response } = await api.DELETE("/api/v1/pipeline/{contact_id}", {
        params: { path: { contact_id: id } },
      });
      if (!response.ok && response.status !== 404) throw new Error("Couldn’t remove it.");
    },
    onMutate: (id) => {
      client.setQueryData<Contact[]>(LIST, (list) => list?.filter((c) => c.id !== id));
    },
    onSettled: () => void refresh(),
  });
}

export function useContactEvents(id: string | null) {
  return useQuery({
    queryKey: ["pipeline", "events", id],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/pipeline/{contact_id}/events", {
          params: { path: { contact_id: id! } },
        }),
      ),
    enabled: Boolean(id),
  });
}
