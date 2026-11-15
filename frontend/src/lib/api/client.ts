import createClient, { type Middleware } from "openapi-fetch";

import type { paths } from "./schema";

// Same-origin: /api/* is forwarded to the backend by next.config.ts.
// Types come from the backend's OpenAPI spec; run `make gen-client` after API changes.
export const api = createClient<paths>({ baseUrl: "", credentials: "include" });

// When the 15-minute access token expires, refresh the session once and retry.
let refreshing: Promise<boolean> | null = null;

export function refreshSession(): Promise<boolean> {
  refreshing ??= fetch("/api/v1/auth/refresh", { method: "POST", credentials: "include" })
    .then((r) => r.ok)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

// Endpoints that create or end a session: a 401 there is the real answer, not an
// expired access token, so never refresh-and-retry them (that would loop).
const SESSION_ENDPOINTS = ["login", "register", "refresh", "logout"].map(
  (name) => `/api/v1/auth/${name}`,
);

const autoRefresh: Middleware = {
  async onResponse({ request, response }) {
    const path = new URL(request.url, "http://x").pathname;
    const retryable = request.method === "GET" || request.method === "HEAD";
    if (response.status !== 401 || SESSION_ENDPOINTS.includes(path) || !retryable) {
      return response;
    }
    return (await refreshSession()) ? fetch(request.url, { credentials: "include" }) : response;
  },
};

api.use(autoRefresh);
