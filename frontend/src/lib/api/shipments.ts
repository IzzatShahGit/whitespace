"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { ApiError, unwrap } from "@/lib/api/queries";
import type { components } from "@/lib/api/schema";

export type Shipment = components["schemas"]["Shipment"];
export type ShipmentDetails = components["schemas"]["ShipmentDetails"];
export type ShipmentSummary = components["schemas"]["ShipmentSummary"];

export function useShipments() {
  return useQuery({ queryKey: ["shipments"], queryFn: () => unwrap(api.GET("/api/v1/shipments")) });
}

export function useShipment(id: string) {
  return useQuery({
    queryKey: ["shipments", id],
    queryFn: () =>
      unwrap(api.GET("/api/v1/shipments/{shipment_id}", { params: { path: { shipment_id: id } } })),
  });
}

/** Opens the documents for a quote's deal (made on first use, the same set afterwards). */
export function useCreateShipment() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (quoteId: string) =>
      unwrap(api.POST("/api/v1/shipments", { body: { quote_id: quoteId } })),
    onSuccess: (s) => {
      client.setQueryData(["shipments", s.id], s);
      void client.invalidateQueries({ queryKey: ["shipments"], exact: true });
    },
  });
}

/** Save details with the version the user saw; a 409 reloads instead of overwriting. */
export function useUpdateShipment(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<ShipmentDetails> & { version: number }) =>
      unwrap(
        api.PATCH("/api/v1/shipments/{shipment_id}", {
          params: { path: { shipment_id: id } },
          // Only changed fields are sent; the server keeps the rest.
          body: body as components["schemas"]["ShipmentPatch"],
        }),
      ),
    onSuccess: (s) => client.setQueryData(["shipments", id], s),
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) {
        void client.invalidateQueries({ queryKey: ["shipments", id] });
      }
    },
  });
}

export function useDeleteShipment() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { response } = await api.DELETE("/api/v1/shipments/{shipment_id}", {
        params: { path: { shipment_id: id } },
      });
      if (!response.ok && response.status !== 404) throw new Error("Couldn’t delete it.");
    },
    onSuccess: () => void client.invalidateQueries({ queryKey: ["shipments"] }),
  });
}
