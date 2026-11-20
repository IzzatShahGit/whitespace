"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { unwrap } from "@/lib/api/queries";
import type { components } from "@/lib/api/schema";

export type Tender = components["schemas"]["Tender"];
export type TendersOut = components["schemas"]["TendersOut"];

/** Open EU tenders for the products in the user's profile. */
export function useMyTenders() {
  return useQuery({
    queryKey: ["tenders", "mine"],
    queryFn: () => unwrap(api.GET("/api/v1/tenders")),
    staleTime: 30 * 60_000,
  });
}

/** EU members whose VAT numbers VIES can check. */
export const EU = new Set([
  "AUT",
  "BEL",
  "BGR",
  "HRV",
  "CYP",
  "CZE",
  "DNK",
  "EST",
  "FIN",
  "FRA",
  "DEU",
  "GRC",
  "HUN",
  "IRL",
  "ITA",
  "LVA",
  "LTU",
  "LUX",
  "MLT",
  "NLD",
  "POL",
  "PRT",
  "ROU",
  "SVK",
  "SVN",
  "ESP",
  "SWE",
]);
