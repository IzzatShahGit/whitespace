"use client";

import { CalendarClock, ExternalLink, Gavel, Info, Landmark } from "lucide-react";

import { Badge, Callout } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button";
import { Card, CardHeader, Page, PageHeader } from "@/components/ui/card";
import { EmptyState, Skeleton } from "@/components/ui/empty";
import { type Tender, useMyTenders } from "@/lib/api/tenders";
import { capitalize } from "@/lib/format";
import { useLocale, useT } from "@/lib/i18n";

function useDay() {
  const { locale } = useLocale();
  return (iso: string) =>
    new Date(`${iso}T00:00:00Z`).toLocaleDateString(locale, {
      day: "numeric",
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    });
}

const value = (tender: Tender) =>
  tender.value && tender.currency
    ? `${tender.currency} ${tender.value.toLocaleString("en", { maximumFractionDigits: 0 })}`
    : null;

export function TenderRow({ tender }: { tender: Tender }) {
  const t = useT();
  const day = useDay();
  const urgent = tender.days_left !== null && tender.days_left <= 7;
  const estimate = value(tender);
  return (
    <li className="flex flex-col gap-2 py-4 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <a
          href={tender.url}
          target="_blank"
          rel="noopener noreferrer"
          className="min-w-0 font-medium text-fg underline-offset-4 hover:underline"
        >
          {tender.title}
          <ExternalLink className="ms-1 inline h-3.5 w-3.5 text-subtle" aria-hidden />
          <span className="sr-only"> (TED)</span>
        </a>
        {tender.deadline && (
          <Badge tone={urgent ? "caution" : "neutral"} icon={<CalendarClock />}>
            {tender.days_left === 0
              ? t("tenders.closesToday")
              : t("tenders.daysLeft", { count: tender.days_left ?? "" })}
          </Badge>
        )}
      </div>
      <p className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
        <span className="inline-flex items-center gap-1">
          <Landmark className="h-3.5 w-3.5" aria-hidden /> {tender.buyer}
        </span>
        <span>{tender.country_names.join(", ")}</span>
        {tender.deadline && <span>{t("tenders.bidsBy", { date: day(tender.deadline) })}</span>}
        {estimate && <span>{t("tenders.estimated", { value: estimate })}</span>}
        <span>{capitalize(tender.product_name)}</span>
      </p>
    </li>
  );
}

/** Public buyers in Europe asking for the user's products right now. */
export function TendersView() {
  const t = useT();
  const tenders = useMyTenders();
  const data = tenders.data;
  return (
    <Page>
      <PageHeader title={t("tenders.title")} description={t("tenders.description")} />
      <Callout tone="neutral">
        <span className="flex gap-2">
          <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <span>{t("tenders.note")}</span>
        </span>
      </Callout>
      <Card className="p-5 sm:p-6">
        <CardHeader
          icon={<Gavel />}
          title={
            data
              ? t("tenders.openFor", {
                  count: data.tenders.length,
                  products: data.products.join(", "),
                })
              : t("tenders.title")
          }
          description={data?.stale ? t("tenders.stale") : t("tenders.matchNote")}
        />
        <div className="mt-6">
          {tenders.isPending ? (
            <Skeleton className="h-40" />
          ) : tenders.isError ? (
            <p className="text-sm text-muted">{t("common.retry")}</p>
          ) : !data?.products.length ? (
            <EmptyState
              icon={<Gavel />}
              title={t("tenders.addProducts")}
              action={
                <ButtonLink href="/app/settings/business">{t("dashboard.editList")}</ButtonLink>
              }
            >
              {t("tenders.matchNote")}
            </EmptyState>
          ) : data.tenders.length === 0 ? (
            <p className="text-sm text-muted">{t("tenders.none")}</p>
          ) : (
            <ul className="divide-y divide-line">
              {data.tenders.map((tender) => (
                <TenderRow key={tender.number} tender={tender} />
              ))}
            </ul>
          )}
        </div>
      </Card>
    </Page>
  );
}
