"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { unwrap } from "@/lib/api/queries";
import type { components } from "@/lib/api/schema";

export type QuoteIn = components["schemas"]["QuoteIn"];
export type Quote = components["schemas"]["QuoteOut"];
export type QuoteSummary = components["schemas"]["QuoteSummary"];
export type Business = components["schemas"]["BusinessOut"];
export type BusinessIn = components["schemas"]["BusinessIn"];
export type Incoterm = Quote["incoterm"];
export type PaymentTerms = Quote["payment"]["key"];

export const INCOTERMS: { value: Incoterm; label: string; explain: string }[] = [
  { value: "FOB", label: "FOB", explain: "Buyer books and pays the ship from your port." },
  { value: "CFR", label: "CFR", explain: "You pay the sea freight to their port." },
  { value: "CIF", label: "CIF", explain: "Sea freight and insurance to their port." },
  { value: "DAP", label: "DAP", explain: "Delivered and unloaded at their port; duty unpaid." },
];

export const PAYMENT_TERMS: { value: PaymentTerms; label: string }[] = [
  { value: "deposit_30", label: "30% deposit, 70% against documents" },
  { value: "advance", label: "100% in advance" },
  { value: "lc_sight", label: "Letter of credit at sight" },
  { value: "cad", label: "Cash against documents" },
  { value: "open_30", label: "Open account, 30 days" },
];

export function useBusiness() {
  return useQuery({
    queryKey: ["business"],
    queryFn: () => unwrap(api.GET("/api/v1/business")),
  });
}

export function useSaveBusiness() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: BusinessIn) => unwrap(api.PUT("/api/v1/business", { body })),
    onSuccess: (data) => client.setQueryData(["business"], data),
  });
}

/** The quote as it would be issued, re-priced as the form changes. */
export function useQuotePreview(body: QuoteIn | null) {
  return useQuery({
    queryKey: ["quote-preview", body],
    queryFn: () => unwrap(api.POST("/api/v1/quotes/preview", { body: body! })),
    enabled: body !== null,
    placeholderData: keepPreviousData,
    retry: false,
    staleTime: 60_000,
  });
}

export function useCreateQuote() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: QuoteIn) => unwrap(api.POST("/api/v1/quotes", { body })),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["quotes"] }),
  });
}

export function useQuotes() {
  return useQuery({ queryKey: ["quotes"], queryFn: () => unwrap(api.GET("/api/v1/quotes")) });
}

export function useQuote(id: string) {
  return useQuery({
    queryKey: ["quotes", id],
    queryFn: () =>
      unwrap(api.GET("/api/v1/quotes/{quote_id}", { params: { path: { quote_id: id } } })),
  });
}

export function useDeleteQuote() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { response } = await api.DELETE("/api/v1/quotes/{quote_id}", {
        params: { path: { quote_id: id } },
      });
      if (!response.ok && response.status !== 404) throw new Error("Couldn’t delete it.");
    },
    onSuccess: () => void client.invalidateQueries({ queryKey: ["quotes"] }),
  });
}
