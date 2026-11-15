"use client";

import { useSearchParams } from "next/navigation";

import { useProfile } from "@/lib/api/queries";

/**
 * Which exporter country a markets page shows: `?exporter=` when given (advisors
 * comparing countries), otherwise the user's own country from their profile.
 * Callers must sit inside a Suspense boundary (search params).
 */
export function useExporter(): { code: string | undefined; pending: boolean; onboarded: boolean } {
  const params = useSearchParams();
  const profile = useProfile();
  const fromUrl = params.get("exporter")?.toUpperCase();
  return {
    code: fromUrl ?? profile.data?.exporter.code,
    pending: !fromUrl && profile.isPending,
    onboarded: Boolean(profile.data),
  };
}

/** Keep the exporter override in links between markets pages. */
export function withExporter(path: string, override: string | null): string {
  return override ? `${path}?exporter=${override}` : path;
}
