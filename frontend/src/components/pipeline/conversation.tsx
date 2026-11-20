"use client";

import {
  AlertTriangle,
  ArrowRight,
  Check,
  Clipboard,
  Inbox,
  Mail,
  Send,
  Sparkles,
  Trash2,
} from "lucide-react";
import { useId, useState } from "react";

import { Badge, Callout } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/empty";
import { inputClass } from "@/components/ui/field";
import { Segmented } from "@/components/ui/segmented";
import { track } from "@/lib/analytics";
import {
  type Analysis,
  type Message,
  type Purpose,
  useDraftEmail,
  useLogSent,
  useReadReply,
  useRemoveMessage,
  useThread,
} from "@/lib/api/outreach";
import { type Contact, useUpdateContact } from "@/lib/api/pipeline";
import { useT } from "@/lib/i18n";
import { timeAgo } from "@/lib/time";

const PURPOSES: Purpose[] = ["first", "follow_up", "reply"];

function ReplyReading({ analysis, contact }: { analysis: Analysis; contact: Contact }) {
  const t = useT();
  const update = useUpdateContact();
  const next = analysis.suggested_stage;
  return (
    <div className="mt-2 flex flex-col gap-2 border-t border-line pt-2 text-xs leading-5">
      {analysis.red_flags.map((f) => (
        <Callout key={f.code} tone={f.severity === "high" ? "negative" : "caution"}>
          <p className="flex gap-1.5 font-medium">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
            {f.label}
          </p>
          <p dir="auto" className="mt-1 opacity-80">
            “{f.quote}”
          </p>
        </Callout>
      ))}
      {analysis.summary && (
        <p className="flex flex-wrap items-center gap-2 text-fg">
          <Badge tone={analysis.intent === "not_interested" ? "negative" : "brand"}>
            {t(`outreach.intents.${analysis.intent}`)}
          </Badge>
          {analysis.summary}
        </p>
      )}
      {analysis.asks.length > 0 && (
        <div>
          <p className="font-medium text-muted">{t("outreach.theyAsk")}</p>
          <ul className="mt-1 flex flex-col gap-1">
            {analysis.asks.map((a, i) => (
              <li key={i} className="flex gap-1.5">
                <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand" aria-hidden />
                <span>
                  <strong className="font-medium text-fg">{a.detail}</strong>{" "}
                  <span dir="auto" className="text-muted">
                    “{a.quote}”
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {analysis.deadline && (
        <p className="text-caution">{t("outreach.deadline", { when: analysis.deadline })}</p>
      )}
      {analysis.removed > 0 && (
        <p className="text-subtle">{t("outreach.removed", { count: analysis.removed })}</p>
      )}
      {analysis.read_by === "template" && <p className="text-subtle">{t("outreach.rulesOnly")}</p>}
      {next && next !== contact.stage && (
        <Button
          size="sm"
          variant="secondary"
          className="self-start"
          disabled={update.isPending}
          onClick={() => update.mutate({ id: contact.id, version: contact.version, stage: next })}
        >
          <ArrowRight /> {t("outreach.moveTo", { stage: t(`pipeline.stages.${next}`) })}
        </Button>
      )}
    </div>
  );
}

function MessageItem({ message, contact }: { message: Message; contact: Contact }) {
  const t = useT();
  const remove = useRemoveMessage(contact.id);
  const [full, setFull] = useState(false);
  const mine = message.direction === "out";
  const long = message.body.length > 360;
  return (
    <li
      className={`rounded-xl border p-3 text-sm ${
        mine ? "border-brand/20 bg-brand-soft/40 sm:ml-8" : "border-line bg-surface-2/50 sm:mr-8"
      }`}
    >
      <div className="flex items-center justify-between gap-2 text-xs text-muted">
        <span className="inline-flex items-center gap-1 font-medium">
          {mine ? (
            <Send className="h-3 w-3" aria-hidden />
          ) : (
            <Inbox className="h-3 w-3" aria-hidden />
          )}
          {mine ? t("outreach.youSent") : t("outreach.theyReplied")} · {timeAgo(message.created_at)}
        </span>
        <button
          type="button"
          aria-label={t("common.remove")}
          disabled={remove.isPending}
          onClick={() => window.confirm(t("outreach.removeConfirm")) && remove.mutate(message.id)}
          className="text-subtle hover:text-negative"
        >
          <Trash2 className="h-3.5 w-3.5" aria-hidden />
        </button>
      </div>
      {message.subject && (
        <p dir="auto" className="mt-1 font-medium text-fg">
          {message.subject}
        </p>
      )}
      <p
        dir="auto"
        className={`mt-1 leading-6 whitespace-pre-line text-fg/90 ${long && !full ? "line-clamp-4" : ""}`}
      >
        {message.body}
      </p>
      {long && (
        <button
          type="button"
          onClick={() => setFull((f) => !f)}
          className="mt-1 text-xs text-brand hover:underline"
        >
          {full ? t("outreach.showLess") : t("outreach.showAll")}
        </button>
      )}
      {message.analysis && <ReplyReading analysis={message.analysis} contact={contact} />}
    </li>
  );
}

function Composer({ contact, purpose: suggested }: { contact: Contact; purpose: Purpose }) {
  const t = useT();
  const id = useId();
  const thread = useThread(contact.id);
  const draft = useDraftEmail(contact.id);
  const sent = useLogSent(contact.id);
  const [purpose, setPurpose] = useState<Purpose>(suggested);
  const [language, setLanguage] = useState("en");
  const [notes, setNotes] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [editing, setEditing] = useState(false);
  const [copied, setCopied] = useState(false);
  const languages = thread.data?.languages ?? [];

  function write() {
    draft.mutate(
      { purpose, language, notes: notes.trim() || null },
      {
        onSuccess: (d) => {
          setSubject(d.subject);
          setBody(d.body);
          setEditing(true);
          track("email_draft_open");
        },
      },
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

  function logIt() {
    sent.mutate(
      { subject: subject.trim() || null, body, language: draft.data?.language ?? null },
      {
        onSuccess: () => {
          setEditing(false);
          setSubject("");
          setBody("");
          setNotes("");
          draft.reset();
        },
      },
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-muted" htmlFor={`${id}-purpose`}>
          {t("outreach.kind")}
          <select
            id={`${id}-purpose`}
            value={purpose}
            onChange={(e) => setPurpose(e.target.value as Purpose)}
            className={`${inputClass} h-9 py-0 text-sm`}
          >
            {PURPOSES.map((p) => (
              <option key={p} value={p}>
                {t(`outreach.purposes.${p}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted" htmlFor={`${id}-lang`}>
          {t("outreach.language")}
          <select
            id={`${id}-lang`}
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className={`${inputClass} h-9 py-0 text-sm`}
          >
            {languages.map((l) => (
              <option key={l.code} value={l.code}>
                {l.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      {languages[0] && languages[0].code !== "en" && language === "en" && (
        <p className="text-xs text-muted">
          {t("outreach.languageTip", { language: languages[0].name })}
        </p>
      )}
      <label className="flex flex-col gap-1 text-xs text-muted" htmlFor={`${id}-notes`}>
        {t("outreach.notes")}
        <input
          id={`${id}-notes`}
          value={notes}
          maxLength={600}
          dir="auto"
          placeholder={t("outreach.notesPlaceholder")}
          onChange={(e) => setNotes(e.target.value)}
          className={`${inputClass} h-9 text-sm`}
        />
      </label>
      <div className="flex flex-wrap items-center gap-3">
        <Button size="sm" onClick={write} disabled={draft.isPending}>
          <Sparkles /> {draft.isPending ? t("outreach.drafting") : t("outreach.draft")}
        </Button>
        {!editing && (
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="text-xs text-muted underline-offset-4 hover:text-fg hover:underline"
          >
            {t("outreach.writeMyself")}
          </button>
        )}
      </div>
      {draft.isError && (
        <p role="alert" className="text-xs text-negative">
          {draft.error.message}
        </p>
      )}
      {draft.isPending && <Skeleton className="h-40" />}
      {editing && !draft.isPending && (
        <div className="flex flex-col gap-2 rounded-xl border border-line bg-surface-2/50 p-3">
          {draft.data?.drafted_by === "template" && (
            <p className="text-xs text-muted">{t("outreach.templateUsed")}</p>
          )}
          {(draft.data?.checks.length ?? 0) > 0 && (
            <Callout tone="caution">
              <p className="font-medium">{t("outreach.beforeSending")}</p>
              <ul className="mt-1 list-disc ps-5 text-xs">
                {draft.data?.checks.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            </Callout>
          )}
          <input
            aria-label={t("outreach.subject")}
            placeholder={t("outreach.subject")}
            value={subject}
            dir="auto"
            onChange={(e) => setSubject(e.target.value)}
            className={`${inputClass} text-sm`}
          />
          <textarea
            aria-label={t("outreach.message")}
            value={body}
            rows={10}
            dir="auto"
            onChange={(e) => setBody(e.target.value)}
            className={`${inputClass} text-sm leading-6`}
          />
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" variant="secondary" onClick={() => void copy()} disabled={!body}>
              <Clipboard /> {copied ? t("outreach.copied") : t("outreach.copy")}
            </Button>
            <a
              href={`mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`}
              className="inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-fg"
            >
              <Mail className="h-3.5 w-3.5" aria-hidden /> {t("outreach.openMail")}
            </a>
            <Button
              size="sm"
              className="ms-auto"
              onClick={logIt}
              disabled={!body.trim() || sent.isPending}
            >
              <Send /> {t("outreach.iSentIt")}
            </Button>
          </div>
          {sent.isError && <p className="text-xs text-negative">{sent.error.message}</p>}
        </div>
      )}
    </div>
  );
}

function PasteReply({ contact, onDone }: { contact: Contact; onDone: () => void }) {
  const t = useT();
  const id = useId();
  const read = useReadReply(contact.id);
  const [text, setText] = useState("");
  return (
    <div className="flex flex-col gap-2">
      <label className="flex flex-col gap-1 text-xs text-muted" htmlFor={`${id}-reply`}>
        {t("outreach.pasteLabel")}
        <textarea
          id={`${id}-reply`}
          value={text}
          rows={7}
          dir="auto"
          maxLength={10000}
          placeholder={t("outreach.pastePlaceholder")}
          onChange={(e) => setText(e.target.value)}
          className={`${inputClass} text-sm leading-6`}
        />
      </label>
      <Button
        size="sm"
        className="self-start"
        disabled={text.trim().length < 10 || read.isPending}
        onClick={() =>
          read.mutate(text, {
            onSuccess: () => {
              setText("");
              onDone();
            },
          })
        }
      >
        <Sparkles /> {read.isPending ? t("outreach.reading") : t("outreach.read")}
      </Button>
      {read.isError && (
        <p role="alert" className="text-xs text-negative">
          {read.error.message}
        </p>
      )}
      <p className="text-xs text-subtle">{t("outreach.pasteNote")}</p>
    </div>
  );
}

/** The emails with one contact, what their replies ask for, and the next email to send. */
export function Conversation({ contact }: { contact: Contact }) {
  const t = useT();
  const thread = useThread(contact.id);
  const [mode, setMode] = useState<"write" | "paste">("write");

  if (thread.isPending) return <Skeleton className="h-24" />;
  if (thread.isError) {
    return <p className="text-xs text-negative">{thread.error.message}</p>;
  }
  const { messages, next_purpose } = thread.data;
  return (
    <div className="flex flex-col gap-4">
      {messages.length > 0 ? (
        <ol className="flex flex-col gap-2">
          {messages.map((m) => (
            <MessageItem key={m.id} message={m} contact={contact} />
          ))}
        </ol>
      ) : (
        <p className="text-xs text-muted">{t("outreach.empty")}</p>
      )}
      <Segmented
        label={t("outreach.next")}
        value={mode}
        onChange={(v) => setMode(v)}
        items={[
          { value: "write" as const, label: t("outreach.writeTab") },
          { value: "paste" as const, label: t("outreach.pasteTab") },
        ]}
      />
      {mode === "write" ? (
        <Composer key={next_purpose} contact={contact} purpose={next_purpose} />
      ) : (
        <PasteReply contact={contact} onDone={() => setMode("write")} />
      )}
    </div>
  );
}
