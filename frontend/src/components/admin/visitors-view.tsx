"use client";

import { Eye, Lock, X } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { AdminTabs, countryName, n, VisitRow } from "@/components/admin/parts";
import { LoadError } from "@/components/markets/load-error";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, Page, PageHeader } from "@/components/ui/card";
import { EmptyState, Skeleton } from "@/components/ui/empty";
import { Segmented } from "@/components/ui/segmented";
import { type VisitsQuery, useAdminVisits } from "@/lib/api/admin";
import { isMissing } from "@/lib/api/queries";

type Show = NonNullable<VisitsQuery["show"]>;
const SHOW: { value: Show; label: string }[] = [
  { value: "all", label: "Everyone" },
  { value: "anonymous", label: "Not signed in" },
  { value: "signed_in", label: "Signed in" },
];

/** Every visit, newest first: where from, on what, which pages and for how long. */
export function VisitorsView() {
  const search = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const asked = search.get("show") as Show | null;
  const show: Show = asked && SHOW.some((s) => s.value === asked) ? asked : "all";
  const country = search.get("country") ?? undefined;
  const source = search.get("source") ?? undefined;
  const includeTest = search.get("test") === "1";
  const page = Math.max(1, Number(search.get("page")) || 1);
  const visits = useAdminVisits({ show, country, source, include_test: includeTest, page });

  function set(changes: Record<string, string | null>) {
    const next = new URLSearchParams(search);
    for (const [k, v] of Object.entries(changes)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    if (!("page" in changes)) next.delete("page");
    router.replace(`${pathname}${next.size ? `?${next}` : ""}`, { scroll: false });
  }

  if (visits.isError && isMissing(visits.error)) {
    return (
      <Page>
        <EmptyState icon={<Lock />} title="Not available">
          This page is for the site’s admins.
        </EmptyState>
      </Page>
    );
  }
  const data = visits.data;
  const pages = data ? Math.max(1, Math.ceil(data.total / data.per_page)) : 1;
  return (
    <Page>
      <PageHeader
        title="Visitors"
        description="Each visit: the country, the site that sent them, their device, the pages they opened and the time on each. Updates every 30 seconds."
      />
      <AdminTabs />
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Segmented items={SHOW} value={show} onChange={(v) => set({ show: v })} label="Show" />
        <label className="flex items-center gap-2 text-sm text-muted">
          <input
            type="checkbox"
            checked={includeTest}
            onChange={(e) => set({ test: e.target.checked ? "1" : null })}
            className="h-4 w-4 accent-brand"
          />
          Include test and admin accounts
        </label>
      </div>
      {(country || source) && (
        <div className="flex flex-wrap gap-2">
          {country && (
            <Button variant="secondary" size="sm" onClick={() => set({ country: null })}>
              {countryName(country)} <X />
            </Button>
          )}
          {source && (
            <Button variant="secondary" size="sm" onClick={() => set({ source: null })}>
              {source} <X />
            </Button>
          )}
        </div>
      )}

      {visits.isPending ? (
        <Skeleton className="h-96" />
      ) : !data ? (
        <LoadError title="Couldn’t load visits" onRetry={() => void visits.refetch()} />
      ) : data.visits.length === 0 ? (
        <Card className="p-6">
          <EmptyState icon={<Eye />} title="No visits yet">
            Visits appear here as soon as someone opens the site (people with “Do Not Track”
            switched on are never counted).
          </EmptyState>
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3 text-sm sm:px-5">
            <span className="text-muted">
              {n(data.total)} {data.total === 1 ? "visit" : "visits"}
            </span>
            <Badge tone={data.live_now ? "positive" : "neutral"}>
              {n(data.live_now)} on the site now
            </Badge>
          </div>
          {data.visits.map((v) => (
            <VisitRow key={v.id} visit={v} />
          ))}
          {pages > 1 && (
            <div className="flex items-center justify-between gap-3 border-t border-line px-4 py-3 text-sm sm:px-5">
              <Button
                variant="secondary"
                size="sm"
                disabled={page <= 1}
                onClick={() => set({ page: String(page - 1) })}
              >
                Newer
              </Button>
              <span className="text-muted tabular-nums">
                Page {page} of {pages}
              </span>
              <Button
                variant="secondary"
                size="sm"
                disabled={page >= pages}
                onClick={() => set({ page: String(page + 1) })}
              >
                Older
              </Button>
            </div>
          )}
        </Card>
      )}
    </Page>
  );
}
