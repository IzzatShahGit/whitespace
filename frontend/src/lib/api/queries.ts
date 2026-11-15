"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

// ---------- types (all generated from the backend's OpenAPI spec) ----------
type Schemas = components["schemas"];
export type User = Schemas["UserOut"];
export type Country = Schemas["CountryOut"];
export type Product = Schemas["ProductOut"];
export type ProductMatch = Schemas["ProductMatch"];
export type MarketItem = Schemas["MarketItem"];
export type MarketsPage = Schemas["MarketsPage"];
export type MarketDetail = Schemas["MarketDetail"];
export type Supplier = Schemas["SupplierOut"];
export type Profile = Schemas["ProfileOut"];
export type ProfileInput = Schemas["ProfileIn"];
export type Role = ProfileInput["role"];
export type Dashboard = Schemas["Dashboard"];
export type DataWindow = Schemas["DataWindow"];
export type Sector = Schemas["SectorOut"];
export type NicheDetail = Schemas["NicheDetail"];
export type RecentMovement = Schemas["RecentMovement"];

// ---------- errors ----------
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

function detail(error: unknown): string | undefined {
  const value = (error as { detail?: unknown } | undefined)?.detail;
  if (typeof value === "string") return value;
  if (Array.isArray(value) && value[0]?.msg) return String(value[0].msg);
  return undefined;
}

/** Turn an openapi-fetch result into data, or throw an ApiError with the server's message. */
async function unwrap<T>(
  request: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await request;
  if (response.ok && data !== undefined) return data;
  throw new ApiError(response.status, detail(error) ?? "Something went wrong. Please try again.");
}

const isMissing = (e: unknown) => e instanceof ApiError && e.status === 404;

// ---------- cache keys: one place, so invalidation can't drift ----------
export const keys = {
  me: ["me"] as const,
  profile: ["profile"] as const,
  dashboard: ["dashboard"] as const,
  exporters: ["exporters"] as const,
  countries: ["countries"] as const,
  search: (exporter: string, q: string) => ["search", exporter, q] as const,
  markets: (exporter: string, hs6: string) => ["markets", exporter, hs6] as const,
  market: (exporter: string, hs6: string, market: string) =>
    ["markets", exporter, hs6, market] as const,
  recent: (exporter: string, hs6: string, market: string) =>
    ["recent", exporter, hs6, market] as const,
  niches: (exporter: string) => ["niches", exporter] as const,
  niche: (exporter: string, slug: string) => ["niches", exporter, slug] as const,
};

const REFERENCE_DATA = 60 * 60 * 1000; // country lists change with a data release

// ---------- session & profile ----------
export function useMe() {
  return useQuery({
    queryKey: keys.me,
    queryFn: () => unwrap(api.GET("/api/v1/auth/me")),
    retry: false,
  });
}

/** The user's profile, or null if they haven't onboarded yet. */
export function useProfile() {
  return useQuery({
    queryKey: keys.profile,
    queryFn: async () => {
      try {
        return await unwrap(api.GET("/api/v1/me/profile"));
      } catch (e) {
        if (isMissing(e)) return null;
        throw e;
      }
    },
  });
}

export function useSaveProfile() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: ProfileInput) => unwrap(api.PUT("/api/v1/me/profile", { body })),
    onSuccess: (profile) => {
      client.setQueryData(keys.profile, profile);
      // Personal flags and top picks depend on the profile.
      void client.invalidateQueries({ queryKey: keys.dashboard });
      void client.invalidateQueries({ queryKey: ["markets"] });
    },
  });
}

export function useDashboard(enabled: boolean) {
  return useQuery({
    queryKey: keys.dashboard,
    queryFn: () => unwrap(api.GET("/api/v1/me/dashboard")),
    enabled,
  });
}

// ---------- reference data ----------
export function useExporters() {
  return useQuery({
    queryKey: keys.exporters,
    queryFn: () => unwrap(api.GET("/api/v1/countries/exporters")),
    staleTime: REFERENCE_DATA,
  });
}

export function useCountries() {
  return useQuery({
    queryKey: keys.countries,
    queryFn: () => unwrap(api.GET("/api/v1/countries")),
    staleTime: REFERENCE_DATA,
  });
}

// ---------- markets ----------
export function useProductSearch(exporter: string | undefined, q: string) {
  const query = q.trim();
  return useQuery({
    queryKey: keys.search(exporter ?? "", query),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/products/search", {
          params: { query: { exporter: exporter!, q: query, limit: 8 } },
        }),
      ),
    enabled: Boolean(exporter) && query.length >= 2,
    placeholderData: (previous) => previous, // keep old suggestions while typing
  });
}

export const MARKETS_PAGE_SIZE = 20;

export function useMarkets(exporter: string | undefined, hs6: string) {
  return useInfiniteQuery({
    queryKey: keys.markets(exporter ?? "", hs6),
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/api/v1/markets", {
          params: {
            query: { exporter: exporter!, hs6, limit: MARKETS_PAGE_SIZE, offset: pageParam },
          },
        }),
      ),
    initialPageParam: 0,
    getNextPageParam: (last) => {
      const next = last.offset + last.items.length;
      return next < last.total ? next : undefined;
    },
    enabled: Boolean(exporter),
  });
}

export function useMarketDetail(exporter: string | undefined, hs6: string, market: string) {
  return useQuery({
    queryKey: keys.market(exporter ?? "", hs6, market),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/markets/{market}", {
          params: { path: { market }, query: { exporter: exporter!, hs6 } },
        }),
      ),
    enabled: Boolean(exporter),
  });
}

/** Monthly data since the annual rankings. Null when the market has no monthly source. */
export function useRecentMovement(exporter: string | undefined, hs6: string, market: string) {
  return useQuery({
    queryKey: keys.recent(exporter ?? "", hs6, market),
    queryFn: async () => {
      try {
        return await unwrap(
          api.GET("/api/v1/markets/{market}/recent", {
            params: { path: { market }, query: { exporter: exporter!, hs6 } },
          }),
        );
      } catch (e) {
        if (isMissing(e)) return null; // not an EU or US market
        throw e;
      }
    },
    enabled: Boolean(exporter),
    staleTime: 60 * 60 * 1000,
  });
}

// ---------- niches ----------
export function useNiches(exporter: string | undefined) {
  return useQuery({
    queryKey: keys.niches(exporter ?? ""),
    queryFn: () =>
      unwrap(api.GET("/api/v1/niches", { params: { query: { exporter: exporter! } } })),
    enabled: Boolean(exporter),
    staleTime: REFERENCE_DATA,
  });
}

export function useNiche(exporter: string | undefined, slug: string) {
  return useQuery({
    queryKey: keys.niche(exporter ?? "", slug),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/niches/{slug}", {
          params: { path: { slug }, query: { exporter: exporter! } },
        }),
      ),
    enabled: Boolean(exporter),
  });
}
