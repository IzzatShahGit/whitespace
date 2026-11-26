"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

import { IdeasView } from "@/components/ideas/ideas-view";
import { Page, PageHeader } from "@/components/ui/card";
import { useT } from "@/lib/i18n";

/** Signed in: product ideas inside the app shell. */
export function IdeasPage() {
  const t = useT();
  return (
    <Page>
      <PageHeader title={t("ideas.title")} description={t("ideas.subtitle")} />
      <IdeasView />
    </Page>
  );
}

/** Signed out: the public best-seller page. Outside the signed-in shell, so it brings its
 * own query client (as the FBA calculator page does). */
export function IdeasLanding() {
  const t = useT();
  const [client] = useState(
    () => new QueryClient({ defaultOptions: { queries: { refetchOnWindowFocus: false } } }),
  );
  return (
    <QueryClientProvider client={client}>
      <div className="mx-auto flex w-full max-w-[96rem] flex-col gap-8 px-4 py-8 sm:px-6 sm:py-12 xl:px-10">
        <header className="rise-in max-w-3xl">
          <p className="text-sm font-medium text-brand">{t("ideas.landing.eyebrow")}</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
            {t("ideas.landing.title")}
          </h1>
          <p className="mt-3 text-pretty text-muted sm:text-lg">{t("ideas.landing.lead")}</p>
        </header>
        <IdeasView signedOut />
      </div>
    </QueryClientProvider>
  );
}
