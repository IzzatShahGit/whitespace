// Admin pages: usage overview, accounts, visits, and account actions.
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { ApiError, unwrap } from "@/lib/api/queries";
import type { components, operations } from "@/lib/api/schema";

type Schemas = components["schemas"];
export type AdminStats = Schemas["AdminStats"];
export type UserList = Schemas["UserList"];
export type UserRow = Schemas["UserRow"];
export type UserDetail = Schemas["UserDetail"];
export type VisitOut = Schemas["VisitOut"];
export type VisitList = Schemas["VisitList"];
export type UsersQuery = NonNullable<
  operations["users_api_v1_admin_users_get"]["parameters"]["query"]
>;
export type VisitsQuery = NonNullable<
  operations["visits_api_v1_admin_visits_get"]["parameters"]["query"]
>;

const ADMIN = ["admin"] as const;

export function useAdminStats() {
  return useQuery({
    queryKey: [...ADMIN, "stats"],
    queryFn: () => unwrap(api.GET("/api/v1/admin/stats")),
    retry: false,
    staleTime: 60_000,
  });
}

export function useAdminUsers(query: UsersQuery) {
  return useQuery({
    queryKey: [...ADMIN, "users", query],
    queryFn: () => unwrap(api.GET("/api/v1/admin/users", { params: { query } })),
    retry: false,
    placeholderData: keepPreviousData,
  });
}

export function useAdminUser(id: string) {
  return useQuery({
    queryKey: [...ADMIN, "user", id],
    queryFn: () =>
      unwrap(api.GET("/api/v1/admin/users/{user_id}", { params: { path: { user_id: id } } })),
    retry: false,
  });
}

export function useAdminVisits(query: VisitsQuery) {
  return useQuery({
    queryKey: [...ADMIN, "visits", query],
    queryFn: () => unwrap(api.GET("/api/v1/admin/visits", { params: { query } })),
    retry: false,
    placeholderData: keepPreviousData,
    refetchInterval: 30_000, // "live now" stays live
  });
}

export type AccountAction =
  { kind: "update"; is_active?: boolean; is_test?: boolean } | { kind: "sign_out" };

/** Disable/enable, mark as test/real, or sign out everywhere. */
export function useAccountAction(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (action: AccountAction) => {
      const path = { user_id: id };
      const { response } =
        action.kind === "sign_out"
          ? await api.POST("/api/v1/admin/users/{user_id}/sign-out", { params: { path } })
          : await api.PATCH("/api/v1/admin/users/{user_id}", {
              params: { path },
              body: { is_active: action.is_active, is_test: action.is_test },
            });
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new ApiError(response.status, body?.detail ?? "That didn’t work. Try again.");
      }
    },
    onSuccess: () => client.invalidateQueries({ queryKey: ADMIN }),
  });
}
