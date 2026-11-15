import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

export type User = components["schemas"]["UserOut"];

type Result = { user: User; error?: never } | { user?: never; error: string };

function message(error: unknown, fallback: string): string {
  const detail = (error as { detail?: unknown })?.detail;
  if (typeof detail === "string") return detail;
  // FastAPI validation errors: a list of { msg, loc }
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
  return fallback;
}

export async function signUp(body: {
  email: string;
  full_name: string;
  password: string;
}): Promise<Result> {
  const { data, error } = await api.POST("/api/v1/auth/register", { body });
  return data ? { user: data } : { error: message(error, "Could not create your account") };
}

export async function signIn(body: { email: string; password: string }): Promise<Result> {
  const { data, error } = await api.POST("/api/v1/auth/login", { body });
  return data ? { user: data } : { error: message(error, "Could not sign you in") };
}

export async function signOut(): Promise<void> {
  await api.POST("/api/v1/auth/logout");
}

export async function currentUser(): Promise<User | null> {
  const { data } = await api.GET("/api/v1/auth/me");
  return data ?? null;
}
