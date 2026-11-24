"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

import { FbaCalculator } from "@/components/fba/fba-view";
import { Page, PageHeader } from "@/components/ui/card";
import { useT } from "@/lib/i18n";

/** Signed in: the calculator inside the app shell, with US demand. */
export function FbaPage() {
  const t = useT();
  return (
    <Page>
      <PageHeader title={t("fba.title")} description={t("fba.subtitle")} />
      <FbaCalculator />
    </Page>
  );
}

/** Signed out: the free calculator page, the way most people will first meet the app.
 * Outside the signed-in shell, so it brings its own query client (as the landing demo). */
export function FbaLanding() {
  const t = useT();
  const [client] = useState(
    () => new QueryClient({ defaultOptions: { queries: { refetchOnWindowFocus: false } } }),
  );
  return (
    <QueryClientProvider client={client}>
      <div className="mx-auto flex w-full max-w-[96rem] flex-col gap-8 px-4 py-8 sm:px-6 sm:py-12 xl:px-10">
        <header className="rise-in max-w-3xl">
          <p className="text-sm font-medium text-brand">{t("fba.landing.eyebrow")}</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
            {t("fba.landing.title")}
          </h1>
          <p className="mt-3 text-pretty text-muted sm:text-lg">{t("fba.landing.lead")}</p>
        </header>
        <FbaCalculator signedOut />
      </div>
    </QueryClientProvider>
  );
}
