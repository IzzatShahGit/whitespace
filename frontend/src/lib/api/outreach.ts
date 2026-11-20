"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { Contact } from "@/lib/api/pipeline";
import { unwrap } from "@/lib/api/queries";
import type { components } from "@/lib/api/schema";

type S = components["schemas"];
export type Thread = S["ThreadOut"];
export type Message = S["MessageOut"];
export type Draft = S["DraftOut"];
export type DraftIn = S["DraftIn"];
export type Analysis = S["ReplyAnalysis"];
export type Purpose = S["DraftOut"]["purpose"];

const threadKey = (id: string) => ["pipeline", "messages", id] as const;

export function useThread(id: string, enabled = true) {
  return useQuery({
    queryKey: threadKey(id),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/pipeline/{contact_id}/messages", {
          params: { path: { contact_id: id } },
        }),
      ),
    enabled,
  });
}

/** After a message is saved: the thread reloads and the card shows the new stage. */
function useSaved(id: string) {
  const client = useQueryClient();
  return (saved: S["MessageSaved"]) => {
    client.setQueryData<Contact[]>(["pipeline"], (list) =>
      list?.map((c) => (c.id === saved.contact.id ? saved.contact : c)),
    );
    void client.invalidateQueries({ queryKey: threadKey(id) });
    void client.invalidateQueries({ queryKey: ["pipeline", "summary"] });
    void client.invalidateQueries({ queryKey: ["pipeline", "events", id] });
  };
}

export function useDraftEmail(id: string) {
  return useMutation({
    mutationFn: (body: DraftIn) =>
      unwrap(
        api.POST("/api/v1/pipeline/{contact_id}/draft", {
          params: { path: { contact_id: id } },
          body,
        }),
      ),
  });
}

export function useLogSent(id: string) {
  const saved = useSaved(id);
  return useMutation({
    mutationFn: (body: S["SentIn"]) =>
      unwrap(
        api.POST("/api/v1/pipeline/{contact_id}/messages", {
          params: { path: { contact_id: id } },
          body,
        }),
      ),
    onSuccess: saved,
  });
}

export function useReadReply(id: string) {
  const saved = useSaved(id);
  return useMutation({
    mutationFn: (text: string) =>
      unwrap(
        api.POST("/api/v1/pipeline/{contact_id}/replies", {
          params: { path: { contact_id: id } },
          body: { text },
        }),
      ),
    onSuccess: saved,
  });
}

export function useRemoveMessage(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (messageId: string) => {
      const { response } = await api.DELETE("/api/v1/pipeline/{contact_id}/messages/{message_id}", {
        params: { path: { contact_id: id, message_id: messageId } },
      });
      if (!response.ok && response.status !== 404) throw new Error("Couldn’t remove it.");
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: threadKey(id) });
      void client.invalidateQueries({ queryKey: ["pipeline"], exact: true });
    },
  });
}
