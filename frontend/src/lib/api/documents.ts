"use client";

import { useMutation } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { unwrap } from "@/lib/api/queries";
import type { components } from "@/lib/api/schema";

export type DocCheck = components["schemas"]["DocCheckOut"];

/** Send a PDF or pasted text (and the quote to compare with). Nothing is stored. */
export function useDocumentCheck() {
  return useMutation({
    mutationFn: ({ file, text, quoteId }: { file?: File; text?: string; quoteId?: string }) => {
      const form = new FormData();
      if (file) form.append("file", file);
      if (text) form.append("text", text);
      if (quoteId) form.append("quote_id", quoteId);
      return unwrap(
        api.POST("/api/v1/documents/check", {
          body: {} as components["schemas"]["Body_check_api_v1_documents_check_post"],
          bodySerializer: () => form,
        }),
      );
    },
  });
}
