// Sign-in, sign-up and sign-out for the auth forms (outside the signed-in area).
import { api } from "@/lib/api/client";
import type { User } from "@/lib/api/queries";

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

/** Ask for a reset link. The answer is the same whether or not the email has an account. */
export async function forgotPassword(email: string): Promise<{ error?: string }> {
  const { error, response } = await api.POST("/api/v1/auth/password/forgot", { body: { email } });
  if (response.status === 429) return { error: "Too many requests. Please wait a minute." };
  return error ? { error: message(error, "Couldn’t send the link. Please try again.") } : {};
}

/** Set a new password from an emailed link; signs the user in. */
export async function resetPassword(token: string, new_password: string): Promise<Result> {
  const { data, error } = await api.POST("/api/v1/auth/password/reset", {
    body: { token, new_password },
  });
  return data ? { user: data } : { error: message(error, "Couldn’t reset your password") };
}

/** Which sign-in features the server has turned on. */
export async function providers(): Promise<{ google: boolean; passwordReset: boolean }> {
  const { data } = await api.GET("/api/v1/auth/providers");
  return { google: Boolean(data?.google), passwordReset: Boolean(data?.password_reset) };
}
