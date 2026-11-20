"use client";

import {
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  Info,
  ShieldAlert,
  ShieldCheck,
  ShieldQuestion,
} from "lucide-react";
import { useSearchParams } from "next/navigation";
import { type FormEvent, useId, useState } from "react";

import { DocumentCheck } from "@/components/checks/document-check";
import { replaceSearchParams } from "@/components/markets/url-state";

import { Badge, type Tone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, Page, PageHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/empty";
import { Field, inputClass } from "@/components/ui/field";
import { Segmented } from "@/components/ui/segmented";
import { type BuyerCheck, type Finding, useBuyerCheck, useLatestCheck } from "@/lib/api/checks";
import type { Contact } from "@/lib/api/pipeline";
import { useCountries } from "@/lib/api/queries";
import { EU } from "@/lib/api/tenders";
import { useT } from "@/lib/i18n";
import { timeAgo } from "@/lib/time";

type Verdict = BuyerCheck["verdict"];
const VERDICT_TONE: Record<Verdict, Tone> = {
  green: "positive",
  amber: "caution",
  red: "negative",
};
const VERDICT_ICON = { green: ShieldCheck, amber: ShieldQuestion, red: ShieldAlert };
const FINDING: Record<Finding["severity"], { icon: typeof Info; className: string }> = {
  high: { icon: AlertOctagon, className: "text-negative" },
  medium: { icon: AlertTriangle, className: "text-caution" },
  ok: { icon: CheckCircle2, className: "text-positive" },
  info: { icon: Info, className: "text-muted" },
};

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  const t = useT();
  const Icon = VERDICT_ICON[verdict];
  return (
    <Badge tone={VERDICT_TONE[verdict]} icon={<Icon />}>
      {t(`checks.verdicts.${verdict}`)}
    </Badge>
  );
}

/** Findings, worst first: what, why it matters, the words that raised it, the record. */
export function FindingList({ findings }: { findings: Finding[] }) {
  const t = useT();
  return (
    <ul className="flex flex-col gap-2.5">
      {findings.map((f, i) => {
        const { icon: FIcon, className } = FINDING[f.severity];
        return (
          <li key={`${f.code}-${i}`} className="flex gap-2">
            <FIcon className={`mt-0.5 h-4 w-4 shrink-0 ${className}`} aria-hidden />
            <div className="min-w-0">
              <p className="font-medium text-fg">{f.title}</p>
              <p className="text-xs leading-5 text-muted">{f.detail}</p>
              {f.quote && (
                <p dir="auto" className="mt-0.5 text-xs break-words text-subtle italic">
                  “{f.quote}”
                </p>
              )}
              {f.url && (
                <a
                  href={f.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-0.5 inline-flex items-center gap-1 text-xs text-brand hover:underline"
                >
                  {t("checks.seeRecord")} <ExternalLink className="h-3 w-3" aria-hidden />
                </a>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}

/** The verdict in one coloured line, with what was checked underneath. */
export function VerdictBanner({ verdict, subtitle }: { verdict: Verdict; subtitle: string }) {
  const t = useT();
  const Icon = VERDICT_ICON[verdict];
  return (
    <div
      className={`flex items-start gap-2 rounded-xl px-3 py-2.5 ${
        verdict === "green"
          ? "bg-positive-soft text-positive"
          : verdict === "amber"
            ? "bg-caution-soft text-caution"
            : "bg-negative-soft text-negative"
      }`}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div>
        <p className="font-medium">{t(`checks.headlines.${verdict}`)}</p>
        <p className="text-xs opacity-80">{subtitle}</p>
      </div>
    </div>
  );
}

/** The verdict, every finding (worst first) with its evidence, and what wasn't checked. */
export function CheckReport({ check }: { check: BuyerCheck }) {
  const t = useT();
  const loaded = check.lists.filter((l) => l.names > 0);
  const domains = [check.website_domain, check.email_domain].filter(
    (d, i, all): d is string => Boolean(d) && all.indexOf(d) === i,
  );
  return (
    <div className="flex flex-col gap-3 text-sm">
      <VerdictBanner
        verdict={check.verdict}
        subtitle={[check.name, ...domains, t("checks.checked", { when: timeAgo(check.checked_at) })]
          .filter(Boolean)
          .join(" · ")}
      />
      <FindingList findings={check.findings} />
      {check.sanctions.length > 1 && (
        <details className="text-xs text-muted">
          <summary className="cursor-pointer">
            {t("checks.allMatches", { count: check.sanctions.length })}
          </summary>
          <ul className="mt-1 flex flex-col gap-1 ps-4">
            {check.sanctions.map((s) => (
              <li key={`${s.source}-${s.name}`}>
                {s.url ? (
                  <a href={s.url} target="_blank" rel="noopener noreferrer" className="underline">
                    {s.name}
                  </a>
                ) : (
                  s.name
                )}{" "}
                · {s.source_label} · {t(`checks.grades.${s.grade}`)}
              </li>
            ))}
          </ul>
        </details>
      )}
      <p className="text-xs leading-5 text-subtle">
        {loaded.length > 0 &&
          t("checks.listsUsed", {
            lists: loaded
              .map((l) => `${l.label}${l.loaded_at ? ` (${timeAgo(l.loaded_at)})` : ""}`)
              .join(", "),
          })}{" "}
        {t("checks.limits")}
      </p>
    </div>
  );
}

/** The optional details that make a check sharper: their email address and VAT number. */
function Extras({
  country,
  email,
  vat,
  onEmail,
  onVat,
}: {
  country: string;
  email: string;
  vat: string;
  onEmail: (v: string) => void;
  onVat: (v: string) => void;
}) {
  const t = useT();
  const id = useId();
  return (
    <div className="flex flex-wrap gap-2">
      <input
        id={`${id}-email`}
        type="email"
        value={email}
        maxLength={320}
        onChange={(e) => onEmail(e.target.value)}
        placeholder={t("checks.emailPlaceholder")}
        aria-label={t("checks.email")}
        className={`${inputClass} h-9 w-64 py-0 text-xs`}
      />
      {EU.has(country) && (
        <input
          id={`${id}-vat`}
          value={vat}
          maxLength={20}
          onChange={(e) => onVat(e.target.value)}
          placeholder={t("checks.vatPlaceholder")}
          aria-label={t("checks.vat")}
          className={`${inputClass} h-9 w-56 py-0 text-xs`}
        />
      )}
    </div>
  );
}

/** On a pipeline card: the last check, or a button to run one (website and replies are
 * taken from the card). */
export function ContactCheck({ contact }: { contact: Contact }) {
  const t = useT();
  const run = useBuyerCheck();
  const latest = useLatestCheck(contact.id, Boolean(contact.check_verdict));
  const [email, setEmail] = useState("");
  const [vat, setVat] = useState("");
  const shown = run.data?.contact_id === contact.id ? run.data : latest.data;

  function check() {
    run.mutate({
      name: contact.name,
      country: contact.market,
      contact_id: contact.id,
      email: email.trim() || null,
      vat: vat.trim() || null,
    });
  }

  return (
    <div className="flex flex-col gap-3 rounded-xl bg-surface-2/50 p-3">
      {latest.isPending && contact.check_verdict ? (
        <Skeleton className="h-20" />
      ) : shown ? (
        <CheckReport check={shown} />
      ) : (
        <p className="text-xs leading-5 text-muted">{t("checks.cardIntro")}</p>
      )}
      <Extras country={contact.market} email={email} vat={vat} onEmail={setEmail} onVat={setVat} />
      <Button
        size="sm"
        variant="secondary"
        className="self-start"
        disabled={run.isPending}
        onClick={check}
      >
        <ShieldCheck />{" "}
        {run.isPending ? t("checks.checking") : shown ? t("checks.again") : t("checks.run")}
      </Button>
      {run.isError && (
        <p role="alert" className="text-xs text-negative">
          {run.error.message}
        </p>
      )}
    </div>
  );
}

/** "Is this buyer real?": paste what you know about an inquiry, get a sourced verdict. */
function BuyerForm() {
  const t = useT();
  const id = useId();
  const countries = useCountries();
  const run = useBuyerCheck();
  const [name, setName] = useState("");
  const [country, setCountry] = useState("");
  const [website, setWebsite] = useState("");
  const [email, setEmail] = useState("");
  const [vat, setVat] = useState("");
  const [message, setMessage] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    if (name.trim().length < 2 || !country) return;
    run.mutate({
      name: name.trim(),
      country,
      website: website.trim() || null,
      email: email.trim() || null,
      vat: vat.trim() || null,
      message: message.trim() || null,
    });
  }

  return (
    <div className="grid items-start gap-5 lg:grid-cols-2">
      <Card className="p-5 sm:p-6">
        <form onSubmit={submit} className="flex flex-col gap-4">
          <Field
            id={`${id}-name`}
            label={t("checks.name")}
            value={name}
            required
            minLength={2}
            maxLength={160}
            onChange={(e) => setName(e.target.value)}
            placeholder="Holiday Heimtex GmbH"
          />
          <div className="flex flex-col gap-1.5">
            <label htmlFor={`${id}-country`} className="text-sm font-medium text-fg">
              {t("checks.country")}
            </label>
            <select
              id={`${id}-country`}
              value={country}
              required
              onChange={(e) => setCountry(e.target.value)}
              className={inputClass}
            >
              <option value="">{t("checks.pickCountry")}</option>
              {(countries.data ?? []).map((c) => (
                <option key={c.code} value={c.code}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <Field
            id={`${id}-site`}
            label={t("checks.website")}
            value={website}
            maxLength={255}
            onChange={(e) => setWebsite(e.target.value)}
            placeholder="holiday-heimtex.de"
          />
          <Field
            id={`${id}-email`}
            type="email"
            label={t("checks.email")}
            hint={t("checks.emailHint")}
            value={email}
            maxLength={320}
            onChange={(e) => setEmail(e.target.value)}
            placeholder={t("checks.emailPlaceholder")}
          />
          {EU.has(country) && (
            <Field
              id={`${id}-vat`}
              label={t("checks.vat")}
              value={vat}
              maxLength={20}
              onChange={(e) => setVat(e.target.value)}
              placeholder={t("checks.vatPlaceholder")}
            />
          )}
          <div className="flex flex-col gap-1.5">
            <label htmlFor={`${id}-message`} className="text-sm font-medium text-fg">
              {t("checks.message")}
            </label>
            <textarea
              id={`${id}-message`}
              value={message}
              rows={6}
              dir="auto"
              maxLength={10000}
              onChange={(e) => setMessage(e.target.value)}
              placeholder={t("checks.messagePlaceholder")}
              className={`${inputClass} h-auto py-3 text-sm leading-6`}
            />
          </div>
          <Button type="submit" disabled={run.isPending} className="self-start">
            <ShieldCheck /> {run.isPending ? t("checks.checking") : t("checks.run")}
          </Button>
          {run.isError && (
            <p role="alert" className="text-sm text-negative">
              {run.error.message}
            </p>
          )}
        </form>
      </Card>
      <Card className="p-5 sm:p-6">
        {run.isPending ? (
          <Skeleton className="h-64" />
        ) : run.data ? (
          <CheckReport check={run.data} />
        ) : (
          <div className="flex flex-col gap-2 text-sm leading-6 text-muted">
            <p className="font-medium text-fg">{t("checks.whatTitle")}</p>
            <ul className="list-disc ps-5">
              <li>{t("checks.what1")}</li>
              <li>{t("checks.what2")}</li>
              <li>{t("checks.what3")}</li>
              <li>{t("checks.what4")}</li>
            </ul>
          </div>
        )}
      </Card>
    </div>
  );
}

type Tab = "buyer" | "document";

/** The Check section: a buyer, or the PO / letter of credit they sent. */
export function CheckView() {
  const t = useT();
  const search = useSearchParams();
  const tab: Tab = search.get("tab") === "document" ? "document" : "buyer";
  return (
    <Page>
      <PageHeader
        title={tab === "buyer" ? t("checks.title") : t("docs.title")}
        description={tab === "buyer" ? t("checks.description") : t("docs.description")}
      />
      <Segmented
        label={t("checks.what")}
        value={tab}
        onChange={(next) => replaceSearchParams({ tab: next })}
        items={[
          { value: "buyer" as Tab, label: t("checks.tabBuyer") },
          { value: "document" as Tab, label: t("checks.tabDocument") },
        ]}
      />
      {tab === "buyer" ? <BuyerForm /> : <DocumentCheck />}
    </Page>
  );
}
