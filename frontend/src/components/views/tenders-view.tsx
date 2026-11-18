"use client";

import { CalendarClock, ExternalLink, Gavel, Info, Landmark } from "lucide-react";

import { Badge, Callout } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button";
import { Card, CardHeader, Page, PageHeader } from "@/components/ui/card";
import { EmptyState, Skeleton } from "@/components/ui/empty";
import { type Tender, useMyTenders } from "@/lib/api/tenders";
import { capitalize } from "@/lib/format";

const day = (iso: string) =>
  new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });

const value = (t: Tender) =>
  t.value && t.currency
    ? `${t.currency} ${t.value.toLocaleString("en", { maximumFractionDigits: 0 })}`
    : null;

export function TenderRow({ t }: { t: Tender }) {
  const urgent = t.days_left !== null && t.days_left <= 7;
  return (
    <li className="flex flex-col gap-2 py-4 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <a
          href={t.url}
          target="_blank"
          rel="noopener noreferrer"
          className="min-w-0 font-medium text-fg underline-offset-4 hover:underline"
        >
          {t.title}
          <ExternalLink className="ml-1 inline h-3.5 w-3.5 text-subtle" aria-hidden />
          <span className="sr-only"> (opens TED in a new tab)</span>
        </a>
        {t.deadline && (
          <Badge tone={urgent ? "caution" : "neutral"} icon={<CalendarClock />}>
            {t.days_left === 0 ? "Closes today" : `${t.days_left} days left`}
          </Badge>
        )}
      </div>
      <p className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
        <span className="inline-flex items-center gap-1">
          <Landmark className="h-3.5 w-3.5" aria-hidden /> {t.buyer}
        </span>
        <span>{t.country_names.join(", ")}</span>
        {t.deadline && <span>Bids by {day(t.deadline)}</span>}
        {value(t) && <span>Estimated {value(t)}</span>}
        <span>{capitalize(t.product_name)}</span>
      </p>
    </li>
  );
}

/** Public buyers in Europe asking for the user's products right now. */
export function TendersView() {
  const tenders = useMyTenders();
  const data = tenders.data;
  return (
    <Page>
      <PageHeader
        title="Open tenders"
        description="European public buyers asking for your products right now, from the EU’s official tender journal (TED)."
      />
      <Callout tone="neutral">
        <span className="flex gap-2">
          <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <span>
            Many tenders accept offers from outside the EU, but often through an EU-registered
            supplier. If you can’t bid yourself, the winning importers are your customers: these are
            live signals of who is buying, and when.
          </span>
        </span>
      </Callout>
      <Card className="p-5 sm:p-6">
        <CardHeader
          icon={<Gavel />}
          title={
            data
              ? `${data.tenders.length} open for ${data.products.join(", ") || "your products"}`
              : "Open tenders"
          }
          description={
            data?.stale
              ? "TED isn’t answering right now; showing the last list we fetched."
              : "Only tenders whose title and product category match your products. Soonest deadline first."
          }
        />
        <div className="mt-6">
          {tenders.isPending ? (
            <Skeleton className="h-40" />
          ) : tenders.isError ? (
            <p className="text-sm text-muted">Couldn’t load tenders right now.</p>
          ) : !data?.products.length ? (
            <EmptyState
              icon={<Gavel />}
              title="Add your products first"
              action={<ButtonLink href="/app/settings/business">Edit products</ButtonLink>}
            >
              We look for tenders matching the products in your profile.
            </EmptyState>
          ) : data.tenders.length === 0 ? (
            <p className="text-sm text-muted">
              No open tenders for your products right now. We check daily and will tell you on the
              bell when one appears.
            </p>
          ) : (
            <ul className="divide-y divide-line">
              {data.tenders.map((t) => (
                <TenderRow key={t.number} t={t} />
              ))}
            </ul>
          )}
        </div>
      </Card>
    </Page>
  );
}
