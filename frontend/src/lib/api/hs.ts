"use client";

import { useMutation } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { unwrap } from "@/lib/api/queries";
import type { components } from "@/lib/api/schema";

export type HsResult = components["schemas"]["HsFinderOut"];
export type HsPick = components["schemas"]["HsPick"];

/** Likely HS codes for a description and/or a photo (the photo isn't stored). */
export function useIdentifyProduct() {
  return useMutation({
    mutationFn: ({ description, photo }: { description?: string; photo?: File }) => {
      const form = new FormData();
      if (description) form.append("description", description);
      if (photo) form.append("photo", photo);
      return unwrap(
        api.POST("/api/v1/products/identify", {
          body: {} as components["schemas"]["Body_identify_api_v1_products_identify_post"],
          bodySerializer: () => form,
        }),
      );
    },
  });
}
