"use client";

import { FileSearch, FileUp } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { type FormEvent, useId, useRef, useState } from "react";

import { FindingList, VerdictBanner } from "@/components/checks/buyer-check";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/empty";
import { inputClass } from "@/components/ui/field";
import { type DocCheck, useDocumentCheck } from "@/lib/api/documents";
import { useQuotes } from "@/lib/api/quotes";
import { useT } from "@/lib/i18n";

function DocReport({ check }: { check: DocCheck }) {
  const t = useT();
  const listed = [...(check.terms.documents ?? []), ...(check.terms.conditions ?? [])];
  return (
    <div className="flex flex-col gap-4 text-sm">
      <VerdictBanner
        verdict={check.verdict}
        subtitle={[
          t(`docs.kinds.${check.kind}`),
          check.quote_number ? t("docs.against", { number: check.quote_number }) : null,
          t(`docs.readBy.${check.read_by}`),
        ]
          .filter(Boolean)
          .join(" · ")}
      />
      <FindingList findings={check.findings} />
      {check.fields.length > 0 && (
        <details open className="rounded-xl border border-line p-3">
          <summary className="cursor-pointer text-xs font-medium text-muted">
            {t("docs.whatWeRead")}
          </summary>
          <dl className="mt-2 grid grid-cols-1 gap-x-4 gap-y-2 text-xs sm:grid-cols-2">
            {check.fields.map((f) => (
              <div key={f.label} className="min-w-0">
                <dt className="text-subtle">{f.label}</dt>
                <dd dir="auto" className="font-medium break-words text-fg">
                  {f.value}
                </dd>
                {f.quote && (
                  <dd dir="auto" className="truncate text-subtle italic" title={f.quote}>
                    “{f.quote}”
                  </dd>
                )}
              </div>
            ))}
          </dl>
        </details>
      )}
      {listed.length > 0 && (
        <details className="rounded-xl border border-line p-3 text-xs">
          <summary className="cursor-pointer font-medium text-muted">
            {t("docs.documentsAndConditions", {
              count: listed.length,
            })}
          </summary>
          <ul className="mt-2 flex list-disc flex-col gap-1 ps-5 text-fg/90">
            {listed.map((item, i) => (
              <li key={i} dir="auto">
                {item}
              </li>
            ))}
          </ul>
        </details>
      )}
      <p className="text-xs leading-5 text-subtle">{t("docs.limits")}</p>
    </div>
  );
}

/** Upload or paste the buyer's PO or letter of credit; compare it with one of your quotes. */
export function DocumentCheck() {
  const t = useT();
  const id = useId();
  const quotes = useQuotes();
  const run = useDocumentCheck();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | undefined>();
  const [text, setText] = useState("");
  const [quoteId, setQuoteId] = useState(useSearchParams().get("quote") ?? "");
  const tooBig = (file?.size ?? 0) > 5 * 1024 * 1024;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (tooBig || (!file && text.trim().length < 40)) return;
    run.mutate({ file, text: file ? undefined : text.trim(), quoteId: quoteId || undefined });
  }

  return (
    <div className="grid items-start gap-5 lg:grid-cols-2">
      <Card className="p-5 sm:p-6">
        <form onSubmit={submit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-fg">{t("docs.upload")}</span>
            <input
              ref={input}
              type="file"
              accept="application/pdf"
              className="sr-only"
              id={`${id}-file`}
              onChange={(e) => setFile(e.target.files?.[0])}
            />
            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => input.current?.click()}
              >
                <FileUp /> {file ? t("docs.another") : t("docs.choose")}
              </Button>
              {file && (
                <span className="text-xs text-muted">
                  {file.name} · {(file.size / 1024).toFixed(0)} KB{" "}
                  <button
                    type="button"
                    className="underline hover:text-fg"
                    onClick={() => {
                      setFile(undefined);
                      if (input.current) input.current.value = "";
                    }}
                  >
                    {t("common.remove")}
                  </button>
                </span>
              )}
            </div>
            {tooBig && <p className="text-xs text-negative">{t("docs.tooBig")}</p>}
          </div>
          {!file && (
            <div className="flex flex-col gap-1.5">
              <label htmlFor={`${id}-text`} className="text-sm font-medium text-fg">
                {t("docs.orPaste")}
              </label>
              <textarea
                id={`${id}-text`}
                value={text}
                rows={8}
                dir="auto"
                maxLength={60000}
                onChange={(e) => setText(e.target.value)}
                placeholder={t("docs.pastePlaceholder")}
                className={`${inputClass} h-auto py-3 font-mono text-xs leading-5`}
              />
            </div>
          )}
          <div className="flex flex-col gap-1.5">
            <label htmlFor={`${id}-quote`} className="text-sm font-medium text-fg">
              {t("docs.compareWith")}
            </label>
            <select
              id={`${id}-quote`}
              value={quoteId}
              onChange={(e) => setQuoteId(e.target.value)}
              className={inputClass}
            >
              <option value="">{t("docs.noQuote")}</option>
              {(quotes.data ?? []).map((q) => (
                <option key={q.id} value={q.id}>
                  {q.number} · {q.buyer_name} · USD {Math.round(q.total_usd).toLocaleString()}
                </option>
              ))}
            </select>
          </div>
          <Button type="submit" className="self-start" disabled={run.isPending || tooBig}>
            <FileSearch /> {run.isPending ? t("docs.reading") : t("docs.run")}
          </Button>
          {run.isError && (
            <p role="alert" className="text-sm text-negative">
              {run.error.message}
            </p>
          )}
          <p className="text-xs text-subtle">{t("docs.privacy")}</p>
        </form>
      </Card>
      <Card className="p-5 sm:p-6">
        {run.isPending ? (
          <Skeleton className="h-64" />
        ) : run.data ? (
          <DocReport check={run.data} />
        ) : (
          <div className="flex flex-col gap-2 text-sm leading-6 text-muted">
            <p className="font-medium text-fg">{t("docs.whatTitle")}</p>
            <ul className="list-disc ps-5">
              <li>{t("docs.what1")}</li>
              <li>{t("docs.what2")}</li>
              <li>{t("docs.what3")}</li>
              <li>{t("docs.what4")}</li>
            </ul>
          </div>
        )}
      </Card>
    </div>
  );
}
