"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

// ---------- types (all generated from the backend's OpenAPI spec) ----------
type Schemas = components["schemas"];
export type User = Schemas["UserOut"];
export type Country = Schemas["CountryOut"];
export type Product = Schemas["ProductOut"];
export type MarketItem = Schemas["MarketItem"];
export type MarketsPage = Schemas["MarketsPage"];
export type MarketDetail = Schemas["MarketDetail"];
export type Supplier = Schemas["SupplierOut"];
export type Profile = Schemas["ProfileOut"];
export type ProfileInput = Schemas["ProfileIn"];
export type Role = ProfileInput["role"];
export type Goal = NonNullable<ProfileInput["goal"]>;
export type Dashboard = Schemas["Dashboard"];
export type DataWindow = Schemas["DataWindow"];
export type Sector = Schemas["SectorOut"];
export type NicheDetail = Schemas["NicheDetail"];
export type RecentMovement = Schemas["RecentMovement"];
export type Signal = Schemas["Signal"];
export type Verdict = Schemas["Verdict"];
export type BestMove = Schemas["BestMove"];
export type Brief = Schemas["BriefOut"];
export type BriefContent = Schemas["BriefContent"];
export type Leads = Schemas["LeadsOut"];
export type LeadsContent = Schemas["LeadsContent"];
export type Lead = Schemas["Lead"];
export type LeadSide = Leads["side"];
export type IntroDraft = Schemas["IntroOut"];
export type SourcingPage = Schemas["SourcingPage"];
export type SupplierOption = Schemas["SupplierOption"];
export type SourcingPick = Schemas["SourcingPick"];
export type FxRates = Schemas["FxRates"];
export type ChatThread = Schemas["ChatThreadOut"];
export type ChatThreadDetail = Schemas["ChatThreadDetail"];
export type ChatMessage = Schemas["ChatMessageOut"];
export type ChatEvent = Schemas["ChatEvent"];
export type ChatCard = ChatMessage["cards"][number];

/** A product found by search: `count` is ranked markets (selling) or supplier countries (buying). */
export type ProductOption = Product & { count: number };
export type Mode = "sell" | "buy";

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
export async function unwrap<T>(
  request: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await request;
  if (response.ok && data !== undefined) return data;
  throw new ApiError(response.status, detail(error) ?? "Something went wrong. Please try again.");
}

export const isMissing = (e: unknown) => e instanceof ApiError && e.status === 404;

// ---------- cache keys: one place, so invalidation can't drift ----------
export const keys = {
  leads: (hs6: string, country: string, side: string) => ["leads", hs6, country, side] as const,
  me: ["me"] as const,
  profile: ["profile"] as const,
  dashboard: ["dashboard"] as const,
  exporters: ["exporters"] as const,
  countries: ["countries"] as const,
  search: (mode: Mode, exporter: string, q: string) => ["search", mode, exporter, q] as const,
  sourcing: (buyer: string, hs6: string) => ["sourcing", buyer, hs6] as const,
  fx: ["fx"] as const,
  chatThreads: ["chat", "threads"] as const,
  chatThread: (id: string) => ["chat", "threads", id] as const,
  chatSuggestions: ["chat", "suggestions"] as const,
  markets: (exporter: string, hs6: string) => ["markets", exporter, hs6] as const,
  market: (exporter: string, hs6: string, market: string) =>
    ["markets", exporter, hs6, market] as const,
  recent: (exporter: string, hs6: string, market: string) =>
    ["recent", exporter, hs6, market] as const,
  brief: (exporter: string, hs6: string, market: string) =>
    ["brief", exporter, hs6, market] as const,
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

// ---------- account ----------
export function useUpdateMe() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (full_name: string) =>
      unwrap(api.PATCH("/api/v1/auth/me", { body: { full_name } })),
    onSuccess: (user) => client.setQueryData(keys.me, user),
  });
}

export function useChangePassword() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { current_password: string | null; new_password: string }) =>
      unwrap(api.POST("/api/v1/auth/password", { body })),
    onSuccess: (user) => client.setQueryData(keys.me, user),
  });
}

export function useDeleteAccount() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (password: string | null) => {
      const { response, error } = await api.POST("/api/v1/auth/delete-account", {
        body: { password },
      });
      if (!response.ok) throw new ApiError(response.status, detail(error) ?? "Couldn’t delete");
    },
    onSuccess: () => client.clear(),
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
/** Products by everyday words or HS code. Selling: ranked markets from `exporter`. Buying: suppliers. */
export function useProductSearch(mode: Mode, exporter: string | undefined, q: string) {
  const query = q.trim();
  return useQuery({
    queryKey: keys.search(mode, exporter ?? "", query),
    queryFn: async (): Promise<ProductOption[]> => {
      if (mode === "buy") {
        const found = await unwrap(
          api.GET("/api/v1/sourcing/products/search", {
            params: { query: { q: query, limit: 8 } },
          }),
        );
        return found.map(({ suppliers, ...product }) => ({ ...product, count: suppliers }));
      }
      const found = await unwrap(
        api.GET("/api/v1/products/search", {
          params: { query: { exporter: exporter!, q: query, limit: 8 } },
        }),
      );
      return found.map(({ markets, ...product }) => ({ ...product, count: markets }));
    },
    enabled: (mode === "buy" || Boolean(exporter)) && query.length >= 2,
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

// ---------- AI briefs ----------
const BRIEF_POLL_MS = 2000;

/** The brief's current state; polls while it's being written. */
export function useBrief(exporter: string | undefined, hs6: string, market: string) {
  return useQuery({
    queryKey: keys.brief(exporter ?? "", hs6, market),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/markets/{market}/brief", {
          params: { path: { market }, query: { exporter: exporter!, hs6 } },
        }),
      ),
    enabled: Boolean(exporter),
    refetchInterval: (query) => (query.state.data?.status === "pending" ? BRIEF_POLL_MS : false),
  });
}

/** Ask for a brief to be written (or refreshed). Tokens are only spent on this action. */
export function useRequestBrief(exporter: string | undefined, hs6: string, market: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/markets/{market}/brief", {
          params: { path: { market }, query: { exporter: exporter!, hs6 } },
        }),
      ),
    onSuccess: (brief) => client.setQueryData(keys.brief(exporter ?? "", hs6, market), brief),
  });
}

// ---------- company leads ----------
/** Companies found for a product in a country; polls while the search runs. */
export function useLeads(hs6: string, country: string | undefined, side: LeadSide) {
  return useQuery({
    queryKey: keys.leads(hs6, country ?? "", side),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/countries/{country}/leads", {
          params: { path: { country: country! }, query: { hs6, side } },
        }),
      ),
    enabled: Boolean(country),
    refetchInterval: (query) => (query.state.data?.status === "pending" ? BRIEF_POLL_MS : false),
  });
}

/** Start a company search. Credits are only spent on this action, and shared by everyone. */
export function useRequestLeads(hs6: string, country: string | undefined, side: LeadSide) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/countries/{country}/leads", {
          params: { path: { country: country! }, query: { hs6, side } },
        }),
      ),
    onSuccess: (leads) => client.setQueryData(keys.leads(hs6, country ?? "", side), leads),
  });
}

/** A first-contact email to one company, to edit and send from the user's own inbox. */
export function useDraftIntro() {
  return useMutation({
    mutationFn: (body: Schemas["IntroIn"]) => unwrap(api.POST("/api/v1/leads/intro", { body })),
  });
}

// ---------- buying ----------
/** Where `buyer` can source a product. Null when there's no supplier data for it. */
export function useSourcing(buyer: string | undefined, hs6: string) {
  return useQuery({
    queryKey: keys.sourcing(buyer ?? "", hs6),
    queryFn: () =>
      unwrap(api.GET("/api/v1/sourcing", { params: { query: { buyer: buyer!, hs6 } } })),
    enabled: Boolean(buyer),
  });
}

/** Every currency against the US dollar. Rates update daily, so they're kept for hours. */
export function useFxRates() {
  return useQuery({
    queryKey: keys.fx,
    queryFn: () => unwrap(api.GET("/api/v1/fx")),
    staleTime: 6 * 60 * 60 * 1000,
  });
}

// ---------- the guide ----------
export function useChatThreads() {
  return useQuery({
    queryKey: keys.chatThreads,
    queryFn: () => unwrap(api.GET("/api/v1/chat/threads")),
  });
}

/** One conversation. Polls while a reply is still being written elsewhere (e.g. after a reload). */
export function useChatThread(id: string | undefined, { paused = false } = {}) {
  return useQuery({
    queryKey: keys.chatThread(id ?? ""),
    queryFn: () =>
      unwrap(api.GET("/api/v1/chat/threads/{thread_id}", { params: { path: { thread_id: id! } } })),
    enabled: Boolean(id) && !paused,
    refetchInterval: (query) =>
      query.state.data?.messages.some((m) => m.status === "pending") ? 2000 : false,
  });
}

export function useChatSuggestions() {
  return useQuery({
    queryKey: keys.chatSuggestions,
    queryFn: () => unwrap(api.GET("/api/v1/chat/suggestions")),
  });
}

export function useDeleteThread() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      unwrap(
        api.DELETE("/api/v1/chat/threads/{thread_id}", { params: { path: { thread_id: id } } }),
      ).catch((e) => {
        if (!isMissing(e)) throw e; // already gone is fine
      }),
    onSuccess: (_, id) => {
      client.removeQueries({ queryKey: keys.chatThread(id) });
      void client.invalidateQueries({ queryKey: keys.chatThreads });
    },
  });
}
