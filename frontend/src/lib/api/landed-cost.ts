"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { isMissing, unwrap } from "@/lib/api/queries";
import type { components } from "@/lib/api/schema";

export type DutyComparison = components["schemas"]["DutyComparison"];
export type LandedCost = components["schemas"]["LandedCost"];
export type LandedLine = components["schemas"]["LandedLine"];

const DAY = 24 * 60 * 60 * 1000; // tariff schedules change yearly

export const landedKeys = {
  duties: (exporter: string, hs6: string, market: string) =>
    ["duties", exporter, hs6, market] as const,
  landed: (
    exporter: string,
    hs6: string,
    market: string,
    cost: number,
    freightPct: number | null,
  ) => ["landed", exporter, hs6, market, cost, freightPct] as const,
};

/** Import duty for the exporter vs its rivals. Null when the market isn't covered (404). */
export function useDuties(exporter: string | undefined, hs6: string, market: string) {
  return useQuery({
    queryKey: landedKeys.duties(exporter ?? "", hs6, market),
    queryFn: async () => {
      try {
        return await unwrap(
          api.GET("/api/v1/markets/{market}/duties", {
            params: { path: { market }, query: { exporter: exporter!, hs6 } },
          }),
        );
      } catch (e) {
        if (isMissing(e)) return null;
        throw e;
      }
    },
    enabled: Boolean(exporter),
    staleTime: DAY,
    retry: false, // 503 means the tariff source is down: say so rather than wait
  });
}

/** Price per kg + freight + duty = landed cost, for the user and their rivals. */
export function useLandedCost(
  exporter: string | undefined,
  hs6: string,
  market: string,
  cost: number | undefined,
  freightPct: number | null,
) {
  const rounded = cost === undefined ? 0 : Math.round(cost * 100) / 100;
  return useQuery({
    queryKey: landedKeys.landed(exporter ?? "", hs6, market, rounded, freightPct),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/markets/{market}/landed-cost", {
          params: {
            path: { market },
            query: {
              exporter: exporter!,
              hs6,
              cost_usd_kg: rounded,
              ...(freightPct !== null && { freight_pct: freightPct }),
            },
          },
        }),
      ),
    enabled: Boolean(exporter) && rounded > 0,
    staleTime: DAY,
    placeholderData: keepPreviousData, // no flicker while the user types
    retry: false,
  });
}
