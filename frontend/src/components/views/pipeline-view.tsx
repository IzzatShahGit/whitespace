"use client";

import {
  AlarmClock,
  ArrowLeft,
  Building2,
  ExternalLink,
  FilePlus2,
  Globe,
  History,
  KanbanSquare,
  MailOpen,
  MessagesSquare,
  Ship,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useId, useMemo, useState } from "react";

import { ContactCheck, VerdictBadge } from "@/components/checks/buyer-check";
import { replaceSearchParams } from "@/components/markets/url-state";
import { Conversation } from "@/components/pipeline/conversation";
import { ButtonLink } from "@/components/ui/button";
import { Card, Page, PageHeader } from "@/components/ui/card";
import { EmptyState, Skeleton } from "@/components/ui/empty";
import { inputClass } from "@/components/ui/field";
import { Segmented } from "@/components/ui/segmented";
import { Tabs } from "@/components/ui/tabs";
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

type Filter = "needs" | "active" | "closed";
type Panel = "emails" | "check" | "notes";
const FILTERS: Filter[] = ["needs", "active", "closed"];
const ACTIVE: Stage[] = ["to_contact", "emailed", "replied", "samples", "negotiating"];
const needsYou = (c: Contact) => c.due || c.reply_waiting;
const matches = (c: Contact, f: Filter) =>
  f === "needs"
    ? needsYou(c)
    : f === "active"
      ? ACTIVE.includes(c.stage)
      : !ACTIVE.includes(c.stage);

const fmtDay = (iso: string) =>
  new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });

/** One compact row: who, where, stage, and why it needs you. */
function Row({ contact, selected }: { contact: Contact; selected: boolean }) {
  const t = useT();
  return (
    <li>
      <button
        type="button"
        onClick={() => replaceSearchParams({ contact: contact.id })}
        aria-current={selected ? "true" : undefined}
        className={`flex w-full items-start gap-3 rounded-xl px-3 py-2.5 text-left transition-colors ${
          selected ? "bg-brand-soft" : "hover:bg-surface-2"
        }`}
      >
        <span className="min-w-0 flex-1">
          <span dir="auto" className="block truncate text-sm font-medium text-fg">
            {contact.name}
          </span>
          <span className="block truncate text-xs text-muted">
            {capitalize(contact.product_name)} · {contact.market_name}
          </span>
        </span>
        <span className="flex shrink-0 flex-col items-end gap-1 text-xs">
          <span className="text-muted">{t(`pipeline.stages.${contact.stage}`)}</span>
          {contact.reply_waiting ? (
            <span className="inline-flex items-center gap-1 font-medium text-brand">
              <MailOpen className="h-3 w-3" aria-hidden /> {t("outreach.replyWaiting")}
            </span>
          ) : contact.due && contact.follow_up_on ? (
            <span className="inline-flex items-center gap-1 font-medium text-caution">
              <AlarmClock className="h-3 w-3" aria-hidden /> {fmtDay(contact.follow_up_on)}
            </span>
          ) : null}
        </span>
      </button>
    </li>
  );
}

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

function Notes({ contact }: { contact: Contact }) {
  const t = useT();
  const id = useId();
  const update = useUpdateContact();
  const [note, setNote] = useState(contact.note ?? "");
  // A newer version from the server (another tab, or a reload after a conflict) wins.
  const [synced, setSynced] = useState(contact.version);
  if (synced !== contact.version) {
    setSynced(contact.version);
    setNote(contact.note ?? "");
  }
  return (
    <div className="flex flex-col gap-4">
      <label className="flex flex-col gap-1 text-xs text-muted" htmlFor={`${id}-note`}>
        {t("pipeline.note")}
        <textarea
          id={`${id}-note`}
          value={note}
          rows={3}
          maxLength={2000}
          dir="auto"
          placeholder={t("pipeline.notePlaceholder")}
          onChange={(e) => setNote(e.target.value)}
          onBlur={() =>
            note !== (contact.note ?? "") &&
            update.mutate({ id: contact.id, version: contact.version, note })
          }
          className={`${inputClass} h-auto py-2.5 text-sm`}
        />
      </label>
      <div>
        <p className="mb-2 flex items-center gap-1.5 text-xs font-medium text-muted">
          <History className="h-3.5 w-3.5" aria-hidden /> {t("pipeline.history")}
        </p>
        <Events id={contact.id} />
      </div>
    </div>
  );
}

/** Everything about one company: where it stands, the emails, the check, the notes. */
function Detail({ contact, onBack }: { contact: Contact; onBack: () => void }) {
  const t = useT();
  const id = useId();
  const update = useUpdateContact();
  const remove = useRemoveContact();
  const [panel, setPanel] = useState<Panel>("emails");
  const market = `/app/markets/${contact.hs6}/${contact.market}`;
  const save = (body: Partial<Pick<Contact, "stage" | "follow_up_on">>) =>
    update.mutate({ id: contact.id, version: contact.version, ...body });

  const links = [
    {
      href: `${market}?tab=${contact.side === "suppliers" ? "overview" : "buyers"}`,
      icon: Building2,
      label: t("pipeline.marketAndEmail"),
    },
    {
      href: `/app/quotes/new?${new URLSearchParams({
        hs6: contact.hs6,
        market: contact.market,
        buyer: contact.name,
        contact: contact.id,
      })}`,
      icon: FilePlus2,
      label: t("pipeline.makeQuote"),
    },
    ...(contact.stage === "won"
      ? [
          {
            href: `/app/quotes?contact=${contact.id}`,
            icon: Ship,
            label: t("pipeline.prepareShipment"),
          },
        ]
      : []),
  ];

  return (
    <Card className="flex flex-col gap-5 p-5 sm:p-6">
      <button
        type="button"
        onClick={onBack}
        className="inline-flex items-center gap-1 self-start text-sm text-muted hover:text-fg lg:hidden"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden /> {t("pipeline.title")}
      </button>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 dir="auto" className="text-xl font-semibold tracking-tight">
            {contact.name}
          </h2>
          <p className="mt-0.5 text-sm text-muted">
            {capitalize(contact.product_name)} · {contact.market_name}
            {contact.city ? ` · ${contact.city}` : ""}
            {contact.side === "suppliers" ? " · supplier" : ""}
          </p>
        </div>
        {contact.check_verdict && <VerdictBadge verdict={contact.check_verdict} />}
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-muted" htmlFor={`${id}-stage`}>
          {t("pipeline.stage")}
          <select
            id={`${id}-stage`}
            value={contact.stage}
            disabled={update.isPending}
            onChange={(e) => save({ stage: e.target.value as Stage })}
            className={`${inputClass} h-9 w-44 py-0 text-sm`}
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
              className={`${inputClass} h-9 w-44 py-0 text-sm`}
            />
          </label>
        )}
      </div>
      <div className="-mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
        {links.map(({ href, icon: Icon, label }) => (
          <Link
            key={href}
            href={href}
            className="inline-flex items-center gap-1 text-brand hover:underline"
          >
            <Icon className="h-3.5 w-3.5" aria-hidden /> {label}
          </Link>
        ))}
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
      </div>
      {update.isError && (
        <p role="alert" className="text-xs text-negative">
          {update.error.message}
        </p>
      )}

      <div className="flex flex-col gap-4">
        <Tabs
          label={contact.name}
          value={panel}
          onChange={setPanel}
          items={[
            {
              value: "emails" as Panel,
              icon: <MessagesSquare />,
              label: contact.emails
                ? t("outreach.emails", { count: contact.emails })
                : t("outreach.writeEmail"),
            },
            { value: "check" as Panel, icon: <ShieldCheck />, label: t("checks.cardResult") },
            { value: "notes" as Panel, icon: <History />, label: t("pipeline.notesTab") },
          ]}
        />
        {panel === "emails" && <Conversation contact={contact} />}
        {panel === "check" && <ContactCheck contact={contact} />}
        {panel === "notes" && <Notes key={contact.id} contact={contact} />}
      </div>

      <button
        type="button"
        onClick={() => {
          if (window.confirm(t("pipeline.removeConfirm", { name: contact.name }))) {
            remove.mutate(contact.id);
            onBack();
          }
        }}
        className="inline-flex items-center gap-1 self-end text-xs text-subtle hover:text-negative"
      >
        <Trash2 className="h-3.5 w-3.5" aria-hidden /> {t("common.remove")}
      </button>
    </Card>
  );
}

/** Every company the user is working on: a list on the left, the chosen one on the right
 * (on phones, the list first; choosing a company opens it full width). */
export function PipelineView() {
  const t = useT();
  const pipeline = usePipeline();
  const search = useSearchParams();
  const focus = search.get("contact");
  const contacts = useMemo(() => pipeline.data ?? [], [pipeline.data]);
  const count = (f: Filter) => contacts.filter((c) => matches(c, f)).length;
  const asked = search.get("show") as Filter | null;
  const filter: Filter =
    asked && FILTERS.includes(asked) ? asked : count("needs") ? "needs" : "active";
  const shown = contacts
    .filter((c) => matches(c, filter))
    .sort((a, b) =>
      needsYou(a) !== needsYou(b)
        ? Number(needsYou(b)) - Number(needsYou(a))
        : (a.follow_up_on ?? "9999").localeCompare(b.follow_up_on ?? "9999"),
    );
  const selected = contacts.find((c) => c.id === focus) ?? null;
  const open = selected ?? shown[0] ?? null;

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
        <Skeleton className="h-96" />
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
        <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
          <Card className={`flex flex-col gap-3 p-3 ${selected ? "max-lg:hidden" : ""}`}>
            <Segmented
              label={t("pipeline.show")}
              value={filter}
              onChange={(next) => replaceSearchParams({ show: next })}
              items={[
                {
                  value: "needs" as Filter,
                  label: t("pipeline.needsYou", { count: count("needs") }),
                },
                {
                  value: "active" as Filter,
                  label: t("pipeline.active", { count: count("active") }),
                },
                {
                  value: "closed" as Filter,
                  label: t("pipeline.closed", { count: count("closed") }),
                },
              ]}
            />
            {shown.length ? (
              <ul className="flex flex-col gap-0.5">
                {shown.map((c) => (
                  <Row key={c.id} contact={c} selected={c.id === open?.id} />
                ))}
              </ul>
            ) : (
              <p className="px-3 py-6 text-center text-sm text-muted">
                {filter === "needs" ? t("pipeline.nothingDue") : t("pipeline.nothingActive")}
              </p>
            )}
          </Card>
          {open && (
            <div className={selected ? "" : "max-lg:hidden"}>
              <Detail
                key={open.id}
                contact={open}
                onBack={() => replaceSearchParams({ contact: null })}
              />
            </div>
          )}
        </div>
      )}
    </Page>
  );
}
