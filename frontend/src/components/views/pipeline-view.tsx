"use client";

import {
  AlarmClock,
  Building2,
  ExternalLink,
  FilePlus2,
  Globe,
  History,
  KanbanSquare,
  Ship,
  Mail,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useId, useMemo, useState } from "react";

import { replaceSearchParams } from "@/components/markets/url-state";
import { CompanyCheckBox } from "@/components/pipeline/company-check";
import { Badge } from "@/components/ui/badge";
import { Button, ButtonLink } from "@/components/ui/button";
import { Card, CardHeader, Page, PageHeader } from "@/components/ui/card";
import { EmptyState, Skeleton } from "@/components/ui/empty";
import { inputClass } from "@/components/ui/field";
import { Segmented } from "@/components/ui/segmented";
import {
  type Contact,
  STAGES,
  type Stage,
  useContactEvents,
  usePipeline,
  useRemoveContact,
  useUpdateContact,
} from "@/lib/api/pipeline";
import { capitalize } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { timeAgo } from "@/lib/time";

type Filter = "due" | "active" | Stage;
const ACTIVE: Stage[] = ["to_contact", "emailed", "replied", "samples", "negotiating"];

const fmtDay = (iso: string) =>
  new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });

function Events({ id }: { id: string }) {
  const events = useContactEvents(id);
  if (events.isPending) return <Skeleton className="h-12" />;
  return (
    <ol className="flex flex-col gap-1.5 text-xs text-muted">
      {(events.data ?? []).map((e, i) => (
        <li key={i} className="flex justify-between gap-3">
          <span>{e.detail}</span>
          <span className="shrink-0 text-subtle">{timeAgo(e.created_at)}</span>
        </li>
      ))}
    </ol>
  );
}

function ContactCard({ contact, open }: { contact: Contact; open: boolean }) {
  const t = useT();
  const id = useId();
  const update = useUpdateContact();
  const remove = useRemoveContact();
  const [note, setNote] = useState(contact.note ?? "");
  const [history, setHistory] = useState(false);
  const market = `/app/markets/${contact.hs6}/${contact.market}`;

  // A newer version from the server (another tab, or a reload after a conflict) wins.
  const [synced, setSynced] = useState(contact.version);
  if (synced !== contact.version) {
    setSynced(contact.version);
    setNote(contact.note ?? "");
  }

  const save = (body: Partial<Pick<Contact, "stage" | "note" | "follow_up_on">>) =>
    update.mutate({ id: contact.id, version: contact.version, ...body });

  return (
    <li
      id={`contact-${contact.id}`}
      className={`flex flex-col gap-3 rounded-2xl border bg-surface p-4 ${
        open ? "border-brand/50 ring-4 ring-brand/10" : "border-line"
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p dir="auto" className="font-medium text-fg">
            {contact.name}
          </p>
          <p className="text-xs text-muted">
            {capitalize(contact.product_name)} · {contact.market_name}
            {contact.city ? ` · ${contact.city}` : ""}
            {contact.side === "suppliers" ? " · supplier" : ""}
          </p>
        </div>
        {contact.due ? (
          <Badge tone="caution" icon={<AlarmClock />}>
            {t("pipeline.followUp", {
              date: contact.follow_up_on ? fmtDay(contact.follow_up_on) : "",
            })}
          </Badge>
        ) : (
          contact.follow_up_on && (
            <Badge tone="neutral">
              {t("pipeline.followUp", { date: fmtDay(contact.follow_up_on) })}
            </Badge>
          )
        )}
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-muted" htmlFor={`${id}-stage`}>
          {t("pipeline.stage")}
          <select
            id={`${id}-stage`}
            value={contact.stage}
            disabled={update.isPending}
            onChange={(e) => save({ stage: e.target.value as Stage })}
            className={`${inputClass} h-9 py-0 text-sm`}
          >
            {STAGES.map((s) => (
              <option key={s.value} value={s.value}>
                {t(`pipeline.stages.${s.value}`)}
              </option>
            ))}
          </select>
        </label>
        {ACTIVE.includes(contact.stage) && (
          <label className="flex flex-col gap-1 text-xs text-muted" htmlFor={`${id}-date`}>
            {t("pipeline.followUpOn")}
            <input
              id={`${id}-date`}
              type="date"
              value={contact.follow_up_on ?? ""}
              disabled={update.isPending}
              onChange={(e) => save({ follow_up_on: e.target.value || null })}
              className={`${inputClass} h-9 py-0 text-sm`}
            />
          </label>
        )}
        {contact.stage === "to_contact" && (
          <Button size="sm" variant="secondary" onClick={() => save({ stage: "emailed" })}>
            <Mail /> {t("pipeline.emailedThem")}
          </Button>
        )}
      </div>

      <label className="flex flex-col gap-1 text-xs text-muted" htmlFor={`${id}-note`}>
        {t("pipeline.note")}
        <textarea
          id={`${id}-note`}
          value={note}
          rows={2}
          maxLength={2000}
          dir="auto"
          placeholder={t("pipeline.notePlaceholder")}
          onChange={(e) => setNote(e.target.value)}
          onBlur={() => note !== (contact.note ?? "") && save({ note })}
          className={`${inputClass} text-sm`}
        />
      </label>

      {update.isError && (
        <p role="alert" className="text-xs text-negative">
          {update.error.message}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
        <Link
          href={`${market}?tab=${contact.side === "suppliers" ? "overview" : "buyers"}`}
          className="inline-flex items-center gap-1 text-brand hover:underline"
        >
          <Building2 className="h-3.5 w-3.5" aria-hidden /> {t("pipeline.marketAndEmail")}
        </Link>
        {contact.stage === "won" && (
          <Link
            href={`/app/quotes?contact=${contact.id}`}
            className="inline-flex items-center gap-1 font-medium text-positive hover:underline"
          >
            <Ship className="h-3.5 w-3.5" aria-hidden /> {t("pipeline.prepareShipment")}
          </Link>
        )}
        <Link
          href={`/app/quotes/new?${new URLSearchParams({
            hs6: contact.hs6,
            market: contact.market,
            buyer: contact.name,
            contact: contact.id,
          })}`}
          className="inline-flex items-center gap-1 text-brand hover:underline"
        >
          <FilePlus2 className="h-3.5 w-3.5" aria-hidden /> {t("pipeline.makeQuote")}
        </Link>
        {contact.website && (
          <a
            href={contact.website}
            target="_blank"
            rel="noopener noreferrer nofollow"
            className="inline-flex items-center gap-1 text-muted hover:text-fg"
          >
            <Globe className="h-3.5 w-3.5" aria-hidden /> {t("pipeline.website")}
          </a>
        )}
        {contact.source_url && (
          <a
            href={contact.source_url}
            target="_blank"
            rel="noopener noreferrer nofollow"
            className="inline-flex items-center gap-1 text-muted hover:text-fg"
          >
            <ExternalLink className="h-3.5 w-3.5" aria-hidden /> {t("pipeline.foundAt")}
          </a>
        )}
        <button
          type="button"
          aria-expanded={history}
          onClick={() => setHistory((h) => !h)}
          className="inline-flex items-center gap-1 text-muted hover:text-fg"
        >
          <History className="h-3.5 w-3.5" aria-hidden /> {t("pipeline.history")}
        </button>
        <button
          type="button"
          onClick={() => {
            if (window.confirm(t("pipeline.removeConfirm", { name: contact.name }))) {
              remove.mutate(contact.id);
            }
          }}
          className="ml-auto inline-flex items-center gap-1 text-subtle hover:text-negative"
        >
          <Trash2 className="h-3.5 w-3.5" aria-hidden /> {t("common.remove")}
        </button>
      </div>
      {contact.side === "buyers" && (
        <CompanyCheckBox name={contact.name} country={contact.market} />
      )}
      {history && <Events id={contact.id} />}
    </li>
  );
}

/** Every company the user is working on, by stage, with follow-ups due first. */
export function PipelineView() {
  const t = useT();
  const pipeline = usePipeline();
  const search = useSearchParams();
  const focus = search.get("contact");
  const contacts = useMemo(() => pipeline.data ?? [], [pipeline.data]);
  const due = contacts.filter((c) => c.due);
  const requested = search.get("stage") as Filter | null;
  const filter: Filter = requested ?? (due.length ? "due" : "active");

  useEffect(() => {
    if (focus && contacts.length) {
      document.getElementById(`contact-${focus}`)?.scrollIntoView({ block: "center" });
    }
  }, [focus, contacts.length]);

  const shown = contacts
    .filter((c) =>
      filter === "due"
        ? c.due
        : filter === "active"
          ? ACTIVE.includes(c.stage)
          : c.stage === filter,
    )
    .sort((a, b) =>
      a.due !== b.due
        ? Number(b.due) - Number(a.due)
        : (a.follow_up_on ?? "9999").localeCompare(b.follow_up_on ?? "9999"),
    );
  const count = (f: Filter) =>
    contacts.filter((c) =>
      f === "due" ? c.due : f === "active" ? ACTIVE.includes(c.stage) : c.stage === f,
    ).length;
  const items = [
    { value: "due" as Filter, label: t("pipeline.due", { count: count("due") }) },
    { value: "active" as Filter, label: t("pipeline.active", { count: count("active") }) },
    ...STAGES.map((s) => ({
      value: s.value as Filter,
      label: `${t(`pipeline.stages.${s.value}`)} (${count(s.value)})`,
    })),
  ];

  return (
    <Page>
      <PageHeader
        title={t("pipeline.title")}
        description={t("pipeline.description")}
        actions={
          <ButtonLink href="/app/markets" variant="secondary">
            <Building2 /> {t("pipeline.findCompanies")}
          </ButtonLink>
        }
      />
      {pipeline.isPending ? (
        <Skeleton className="h-64" />
      ) : contacts.length === 0 ? (
        <Card className="p-6">
          <EmptyState
            icon={<KanbanSquare />}
            title={t("pipeline.emptyTitle")}
            action={
              <ButtonLink href="/app/markets" variant="primary">
                {t("pipeline.findBuyers")}
              </ButtonLink>
            }
          >
            {t("pipeline.emptyBody")}
          </EmptyState>
        </Card>
      ) : (
        <Card className="flex flex-col gap-5 p-5 sm:p-6">
          <CardHeader
            icon={<KanbanSquare />}
            title={t("pipeline.summary", { active: count("active"), won: count("won") })}
            description={t("pipeline.summaryDesc")}
          />
          <Segmented
            label={t("pipeline.show")}
            value={filter}
            onChange={(next) => replaceSearchParams({ stage: next })}
            items={items}
          />
          {shown.length ? (
            <ul className="grid gap-3 lg:grid-cols-2">
              {shown.map((c) => (
                <ContactCard key={c.id} contact={c} open={c.id === focus} />
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">
              {filter === "due"
                ? t("pipeline.nothingDue")
                : filter === "active"
                  ? t("pipeline.nothingActive")
                  : t("pipeline.nothingIn", { stage: t(`pipeline.stages.${filter}`) })}
            </p>
          )}
        </Card>
      )}
    </Page>
  );
}
