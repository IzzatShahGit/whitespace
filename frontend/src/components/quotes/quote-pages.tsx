"use client";

import { ArrowLeft, FilePlus2, FileText, Printer, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { use } from "react";

import { QuoteDocument } from "@/components/quotes/quote-document";
import { Button, ButtonLink } from "@/components/ui/button";
import { Card, Page, PageHeader } from "@/components/ui/card";
import { EmptyState, Skeleton } from "@/components/ui/empty";
import { track } from "@/lib/analytics";
import { useDeleteQuote, useQuote, useQuotes } from "@/lib/api/quotes";

const usd = (n: number) => `US$${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;

/** One issued quote, ready to print or save as PDF. */
export function QuoteView({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const quote = useQuote(id);
  const remove = useDeleteQuote();
  if (quote.isPending)
    return (
      <Page>
        <Skeleton className="h-[40rem]" />
      </Page>
    );
  if (!quote.data) {
    return (
      <Page>
        <EmptyState icon={<FileText />} title="Quote not found">
          It may have been deleted.
        </EmptyState>
      </Page>
    );
  }
  const q = quote.data;
  return (
    <Page className="gap-5">
      <div className="no-print flex flex-wrap items-center justify-between gap-3">
        <Link
          href="/app/quotes"
          className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-fg"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden /> All quotes
        </Link>
        <div className="flex gap-2">
          <Button
            variant="ghost"
            onClick={() => {
              if (window.confirm(`Delete ${q.number}?`)) {
                remove.mutate(id, { onSuccess: () => router.push("/app/quotes") });
              }
            }}
          >
            <Trash2 /> Delete
          </Button>
          <Button
            onClick={() => {
              track("deal_sheet_print");
              window.print();
            }}
          >
            <Printer /> Print / PDF
          </Button>
        </div>
      </div>
      <div className="mx-auto w-full max-w-3xl">
        <QuoteDocument quote={q} />
      </div>
      {q.seller_notes.length > 0 && (
        <Card className="no-print mx-auto w-full max-w-3xl p-4 text-xs leading-5 text-muted">
          <p className="mb-1 font-medium text-fg">Only you see these notes</p>
          <ul className="list-disc pl-4">
            {q.seller_notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </Card>
      )}
    </Page>
  );
}

/** Every quote and proforma the user issued. */
export function QuotesList() {
  const quotes = useQuotes();
  return (
    <Page>
      <PageHeader
        title="Quotes"
        description="Quotes and proforma invoices you’ve issued. Each keeps the prices it was issued with."
        actions={
          <ButtonLink href="/app/quotes/new">
            <FilePlus2 /> New quote
          </ButtonLink>
        }
      />
      {quotes.isPending ? (
        <Skeleton className="h-48" />
      ) : !quotes.data?.length ? (
        <Card className="p-6">
          <EmptyState
            icon={<FileText />}
            title="No quotes yet"
            action={<ButtonLink href="/app/quotes/new">Make your first quote</ButtonLink>}
          >
            Turn a deal sheet into a quote buyers can sign: FOB, CFR, CIF or DAP, with your payment
            terms.
          </EmptyState>
        </Card>
      ) : (
        <Card className="p-2 sm:p-3">
          <ul className="divide-y divide-line">
            {quotes.data.map((q) => (
              <li key={q.id}>
                <Link
                  href={`/app/quotes/${q.id}`}
                  className="flex items-center justify-between gap-3 rounded-xl px-3 py-3 transition-colors hover:bg-surface-2"
                >
                  <span className="min-w-0">
                    <span className="block truncate font-medium">{q.buyer_name}</span>
                    <span className="text-xs text-muted">
                      {q.number} · {q.kind === "proforma" ? "Proforma" : "Quote"} ·{" "}
                      {new Date(q.created_at).toLocaleDateString("en-GB")}
                    </span>
                  </span>
                  <span className="shrink-0 font-medium tabular-nums">{usd(q.total_usd)}</span>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </Page>
  );
}
