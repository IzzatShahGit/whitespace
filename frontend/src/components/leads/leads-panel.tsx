"use client";

import {
  BookmarkCheck,
  BookmarkPlus,
  Building2,
  CalendarDays,
  Check,
  Copy,
  ExternalLink,
  Globe,
  Mail,
  MapPin,
  RefreshCw,
  Search,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/empty";
import { track } from "@/lib/analytics";
import { sameCompany, useAddContact, usePipeline } from "@/lib/api/pipeline";
import { useT } from "@/lib/i18n";
import { Segmented } from "@/components/ui/segmented";
import {
  type Lead,
  type LeadSide,
  type LeadsContent,
  useDraftIntro,
  useLeads,
  useRequestLeads,
} from "@/lib/api/queries";

const KIND_LABEL: Record<Lead["kind"], string> = {
  importer: "Importer",
  distributor: "Distributor",
  wholesaler: "Wholesaler",
  retailer: "Retailer",
  brand: "Brand",
  manufacturer: "Manufacturer",
  exporter: "Exporter",
  agent: "Agent",
  other: "Company",
};

const PROGRESS = {
  buyers: [
    "Searching business directories…",
    "Searching in the local language…",
    "Reading importer and distributor lists…",
    "Checking every name against its page…",
  ],
  suppliers: [
    "Searching manufacturer directories…",
    "Searching in the local language…",
    "Reading supplier lists…",
    "Checking every name against its page…",
  ],
};

function Progress({ side }: { side: LeadSide }) {
  const steps = PROGRESS[side];
  const [step, setStep] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setStep((s) => Math.min(s + 1, steps.length - 1)), 5000);
    return () => clearInterval(id);
  }, [steps.length]);
  return (
    <div aria-live="polite" className="flex flex-col gap-3">
      <p className="text-sm text-muted">{steps[step]}</p>
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-16 w-5/6" />
    </div>
  );
}

function webSearch(name: string, countryName: string) {
  return `https://www.google.com/search?q=${encodeURIComponent(`"${name}" ${countryName}`)}`;
}

const linkClass =
  "inline-flex items-center gap-1 rounded text-xs font-medium text-muted underline-offset-4 hover:text-fg hover:underline focus-visible:outline-2 focus-visible:outline-brand";

/** The drafted first email: editable, then copied or opened in the user's mail app. */
function IntroBox({
  lead,
  hs6,
  country,
  side,
}: {
  lead: Lead;
  hs6: string;
  country: string;
  side: LeadSide;
}) {
  const draft = useDraftIntro();
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [copied, setCopied] = useState(false);
  const { mutate } = draft;

  useEffect(() => {
    mutate(
      { hs6, country, side, company: lead.name, kind: lead.kind, handles: lead.handles },
      {
        onSuccess: (d) => {
          setSubject(d.subject);
          setBody(d.body);
        },
      },
    );
  }, [mutate, hs6, country, side, lead.name, lead.kind, lead.handles]);

  if (draft.isPending) {
    return (
      <div className="mt-3 flex flex-col gap-2" aria-busy>
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }
  if (draft.isError) {
    return (
      <p role="alert" className="mt-3 text-sm text-negative">
        {draft.error.message}
      </p>
    );
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(`Subject: ${subject}\n\n${body}`);
      track("intro_copy");
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  const mailto = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  return (
    <div className="mt-3 flex flex-col gap-2 rounded-xl border border-line bg-surface-2/50 p-3">
      <label className="text-xs font-medium text-muted" htmlFor={`subject-${lead.name}`}>
        Subject
      </label>
      <input
        id={`subject-${lead.name}`}
        value={subject}
        onChange={(e) => setSubject(e.target.value)}
        className="rounded-lg border border-line bg-surface px-3 py-2 text-sm text-fg focus-visible:outline-2 focus-visible:outline-brand"
      />
      <label className="text-xs font-medium text-muted" htmlFor={`body-${lead.name}`}>
        Message
      </label>
      <textarea
        id={`body-${lead.name}`}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        rows={9}
        dir="auto"
        className="rounded-lg border border-line bg-surface px-3 py-2 text-sm leading-6 text-fg focus-visible:outline-2 focus-visible:outline-brand"
      />
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant="secondary" onClick={() => void copy()}>
          {copied ? <Check /> : <Copy />} {copied ? "Copied" : "Copy"}
        </Button>
        <a href={mailto} className={linkClass} onClick={() => track("email_draft_open")}>
          <Mail className="h-3.5 w-3.5" aria-hidden /> Open in my email app
        </a>
      </div>
      <p className="text-xs text-subtle">
        Fill in the [brackets] and find their address on their website’s contact page.
        {draft.data?.drafted_by === "template" && " (Our AI was busy, so this is a template.)"}
      </p>
    </div>
  );
}

/** Save a company to the user's pipeline; shows when it's already there. */
function SaveToPipeline({
  lead,
  hs6,
  country,
  side,
  sourceUrl,
}: {
  lead: Lead;
  hs6: string;
  country: string;
  side: LeadSide;
  sourceUrl?: string;
}) {
  const t = useT();
  const pipeline = usePipeline();
  const add = useAddContact();
  const saved = pipeline.data?.some(
    (c) => c.hs6 === hs6 && c.market === country && sameCompany(c.name, lead.name),
  );
  if (saved || add.isSuccess) {
    return (
      <Link href="/app/pipeline" className={`${linkClass} text-positive`}>
        <BookmarkCheck className="h-3.5 w-3.5" aria-hidden /> {t("pipeline.inPipeline")}
      </Link>
    );
  }
  return (
    <button
      type="button"
      disabled={add.isPending}
      onClick={() =>
        add.mutate({
          hs6,
          market: country,
          side,
          name: lead.name,
          kind: lead.kind,
          city: lead.city ?? null,
          website: lead.website ?? null,
          source_url: sourceUrl ?? null,
        })
      }
      className={`${linkClass} text-brand`}
    >
      <BookmarkPlus className="h-3.5 w-3.5" aria-hidden />
      {add.isError ? t("common.retry") : t("pipeline.saveToPipeline")}
    </button>
  );
}

function LeadRow({
  lead,
  content,
  hs6,
  country,
  countryName,
  side,
}: {
  lead: Lead;
  content: LeadsContent;
  hs6: string;
  country: string;
  countryName: string;
  side: LeadSide;
}) {
  const [writing, setWriting] = useState(false);
  const source = content.sources.find((s) => s.id === lead.source);
  return (
    <li className="py-4 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span dir="auto" className="font-medium text-fg">
              {lead.name}
            </span>
            <Badge
              tone={lead.kind === "importer" || lead.kind === "distributor" ? "brand" : "neutral"}
            >
              {KIND_LABEL[lead.kind]}
            </Badge>
          </div>
          <p dir="auto" className="mt-1 text-sm text-muted">
            {lead.handles}
            {lead.city && (
              <span className="ml-2 inline-flex items-center gap-1 text-subtle">
                <MapPin className="h-3.5 w-3.5" aria-hidden />
                {lead.city}
              </span>
            )}
          </p>
        </div>
        <div className="hidden sm:block">
          <Button
            size="sm"
            variant={writing ? "secondary" : "ghost"}
            aria-expanded={writing}
            onClick={() => setWriting((w) => !w)}
          >
            <Mail /> {writing ? "Close" : "Draft email"}
          </Button>
        </div>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
        <SaveToPipeline
          lead={lead}
          hs6={hs6}
          country={country}
          side={side}
          sourceUrl={source?.url}
        />
        {/* Phones: the email action sits with the links instead of beside the name. */}
        <button
          type="button"
          aria-expanded={writing}
          onClick={() => setWriting((w) => !w)}
          className={`${linkClass} text-brand sm:hidden`}
        >
          <Mail className="h-3.5 w-3.5" aria-hidden /> {writing ? "Close email" : "Draft email"}
        </button>
        {lead.website && (
          <a
            href={lead.website}
            target="_blank"
            rel="noopener noreferrer nofollow"
            className={linkClass}
          >
            <Globe className="h-3.5 w-3.5" aria-hidden /> Website
          </a>
        )}
        <a
          href={webSearch(lead.name, countryName)}
          target="_blank"
          rel="noopener noreferrer nofollow"
          className={linkClass}
        >
          <Search className="h-3.5 w-3.5" aria-hidden /> Look them up
        </a>
        {source && (
          <a
            href={source.url}
            target="_blank"
            rel="noopener noreferrer nofollow"
            className={linkClass}
          >
            <ExternalLink className="h-3.5 w-3.5" aria-hidden /> Found on {source.domain}
          </a>
        )}
      </div>
      {writing && <IntroBox lead={lead} hs6={hs6} country={country} side={side} />}
    </li>
  );
}

function LeadsBody({
  content,
  hs6,
  country,
  countryName,
  side,
}: {
  content: LeadsContent;
  hs6: string;
  country: string;
  countryName: string;
  side: LeadSide;
}) {
  const kinds = useMemo(
    () => [...new Set(content.companies.map((c) => c.kind))],
    [content.companies],
  );
  const [kind, setKind] = useState<string>("all");
  const shown = content.companies.filter((c) => kind === "all" || c.kind === kind);

  if (content.companies.length === 0) {
    return (
      <p className="text-sm text-muted">
        We couldn’t find companies named on the web pages we searched. Try the directories in the
        sources below, or ask the AI guide for local trade associations.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {kinds.length > 1 && (
        <Segmented
          label="Filter by type"
          value={kind}
          onChange={setKind}
          items={[
            { value: "all", label: `All ${content.companies.length}` },
            ...kinds.map((k) => ({
              value: k,
              label: `${KIND_LABEL[k]} ${content.companies.filter((c) => c.kind === k).length}`,
            })),
          ]}
        />
      )}

      <ul className="flex flex-col divide-y divide-line">
        {shown.map((lead) => (
          <LeadRow
            key={lead.name}
            lead={lead}
            content={content}
            hs6={hs6}
            country={country}
            countryName={countryName}
            side={side}
          />
        ))}
      </ul>

      {content.events.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-fg">Trade fairs to meet them</h3>
          <ul className="mt-3 grid gap-2 sm:grid-cols-2">
            {content.events.map((e) => {
              const source = content.sources.find((s) => s.id === e.source);
              return (
                <li key={e.name} className="flex gap-3 rounded-xl border border-line p-3">
                  <CalendarDays className="mt-0.5 h-4 w-4 shrink-0 text-brand" aria-hidden />
                  <span className="min-w-0 text-sm">
                    <span className="block font-medium text-fg">{e.name}</span>
                    <span className="block text-muted">
                      {[e.city, e.when].filter(Boolean).join(" · ") || "Dates on their site"}
                    </span>
                    {source && (
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer nofollow"
                        className={linkClass}
                      >
                        {source.domain}
                      </a>
                    )}
                  </span>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      <details className="group">
        <summary className="cursor-pointer text-sm font-medium text-muted hover:text-fg">
          {content.sources.length} pages searched
        </summary>
        <ol className="mt-2 flex flex-col gap-1.5 text-sm">
          {content.sources.map((s) => (
            <li key={s.id} className="min-w-0 truncate">
              <a
                href={s.url}
                target="_blank"
                rel="noopener noreferrer nofollow"
                className={linkClass}
              >
                {s.title || s.domain}
              </a>
              <span className="ml-2 text-xs text-subtle">{s.domain}</span>
            </li>
          ))}
        </ol>
      </details>
    </div>
  );
}

/** Companies to contact: importers in a market (selling) or makers in a country (buying). */
export function LeadsPanel({
  hs6,
  country,
  countryName,
  productName,
  side,
}: {
  hs6: string;
  country: string;
  countryName: string;
  productName: string;
  side: LeadSide;
}) {
  const leads = useLeads(hs6, country, side);
  const request = useRequestLeads(hs6, country, side);
  const status = leads.data?.status;
  const buying = side === "suppliers";

  return (
    <Card className="p-5 sm:p-6">
      <CardHeader
        icon={<Building2 />}
        title={buying ? `Who to buy from in ${countryName}` : `Who to contact in ${countryName}`}
        description={
          buying
            ? `Manufacturers and exporters of ${productName}, found on the web.`
            : `Importers, distributors and brands that deal in ${productName}, found on the web.`
        }
        action={
          status === "ready" && leads.data?.stale ? (
            <Button
              variant="secondary"
              size="sm"
              disabled={request.isPending}
              onClick={() => request.mutate()}
            >
              <RefreshCw /> Refresh
            </Button>
          ) : undefined
        }
      />

      <div className="mt-6">
        {leads.isPending && (
          <div className="flex flex-col gap-3" aria-busy>
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        )}

        {leads.isError && (
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-sm text-muted">Couldn’t check for companies.</p>
            <Button variant="secondary" size="sm" onClick={() => void leads.refetch()}>
              Try again
            </Button>
          </div>
        )}

        {(status === "missing" || status === "failed") && (
          <div className="flex flex-col gap-4 rounded-2xl border border-dashed border-line-strong/60 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
            <div>
              <p className="font-medium">
                {status === "failed"
                  ? "The last search didn’t finish"
                  : buying
                    ? `Find ${productName} makers in ${countryName}`
                    : `Find ${productName} buyers in ${countryName}`}
              </p>
              <p className="mt-1 text-sm text-muted">
                {status === "failed"
                  ? (leads.data?.error ?? "Please try again.")
                  : "We search directories and company sites (in English and the local language) and keep only companies we can see named on the page. About 20 seconds."}
              </p>
            </div>
            <Button
              variant="secondary"
              className="shrink-0"
              disabled={request.isPending}
              onClick={() => request.mutate()}
            >
              <Search /> {status === "failed" ? "Try again" : "Find companies"}
            </Button>
          </div>
        )}

        {request.isError && (
          <p role="alert" className="mt-3 text-sm text-negative">
            {request.error.message}
          </p>
        )}

        {status === "pending" && <Progress side={side} />}

        {status === "ready" && leads.data?.content && (
          <>
            <LeadsBody
              content={leads.data.content}
              hs6={hs6}
              country={country}
              countryName={countryName}
              side={side}
            />
            <p className="mt-7 flex gap-2 border-t border-line pt-4 text-xs leading-5 text-subtle">
              <ShieldCheck className="h-4 w-4 shrink-0" aria-hidden />
              <span>
                Found {leads.data.generated_at?.slice(0, 10)}. Every company is named on the page we
                link. These are leads, not verified {buying ? "suppliers" : "buyers"}: check a
                company’s registration and references before sending samples or paying.
              </span>
            </p>
          </>
        )}
      </div>
    </Card>
  );
}
