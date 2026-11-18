"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";

import { replaceSearchParams } from "@/components/markets/url-state";
import { api } from "@/lib/api/client";
import { isMissing, unwrap } from "@/lib/api/queries";
import type { components } from "@/lib/api/schema";

export type FreightEstimate = components["schemas"]["FreightEstimate"];
export type ContainerKind = FreightEstimate["container"];
export type CostRange = components["schemas"]["CostRange"];

const HOUR = 60 * 60 * 1000;
const KINDS: ContainerKind[] = ["20ft", "40ft", "40hc", "lcl"];

/** The size picker. "lcl": a share of a container, for small orders. */
export const CONTAINER_OPTIONS: { value: ContainerKind; label: string }[] = [
  { value: "lcl", label: "Shared" },
  { value: "20ft", label: "20ft" },
  { value: "40ft", label: "40ft" },
  { value: "40hc", label: "40ft HC" },
];

/** "a 20ft container", "a shared container (LCL)": for sentences. */
export function boxName(kind: ContainerKind): string {
  if (kind === "lcl") return "a shared container (LCL)";
  if (kind === "40hc") return "a 40ft high-cube container";
  return `a ${kind} container`;
}

/**
 * The shipping choice, kept in the URL (?ship=20ft&load=8000) so every panel agrees.
 * `load` is kg per container, or the whole shipment when sharing a container.
 */
export function useShipping() {
  const search = useSearchParams();
  const ship = search.get("ship");
  const container: ContainerKind = KINDS.includes(ship as ContainerKind)
    ? (ship as ContainerKind)
    : "40ft";
  const loadValue = Number(search.get("load"));
  const load = loadValue > 0 && loadValue <= 30_000 ? loadValue : null;
  return {
    container,
    load,
    setContainer: (next: ContainerKind) =>
      replaceSearchParams({ ship: next === "40ft" ? null : next }),
    setLoad: (next: number | null) => replaceSearchParams({ load: next ? String(next) : null }),
  };
}

/** One container's cost from `origin` to `dest`. Null when there's no route (404). */
export function useFreight(
  origin: string | undefined,
  dest: string,
  hs6: string,
  container: ContainerKind,
  load: number | null,
  valueUsdKg?: number,
) {
  const value = valueUsdKg ? Math.round(valueUsdKg * 100) / 100 : undefined;
  return useQuery({
    queryKey: ["freight", origin ?? "", dest, hs6, container, load, value ?? null] as const,
    queryFn: async () => {
      try {
        return await unwrap(
          api.GET("/api/v1/freight", {
            params: {
              query: {
                origin: origin!,
                dest,
                hs6,
                container,
                ...(load !== null && { kg_per_container: load }),
                ...(value !== undefined && { value_usd_kg: value }),
              },
            },
          }),
        );
      } catch (error) {
        if (isMissing(error)) return null;
        throw error;
      }
    },
    enabled: Boolean(origin) && origin !== dest,
    staleTime: HOUR,
    placeholderData: keepPreviousData,
    retry: false,
  });
}
