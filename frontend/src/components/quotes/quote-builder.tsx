"use client";

import { Info, LoaderCircle, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { QuoteDocument } from "@/components/quotes/quote-document";
import { Callout } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, Page, PageHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/empty";
import { inputClass } from "@/components/ui/field";
import { Segmented } from "@/components/ui/segmented";
import { CONTAINER_OPTIONS, type ContainerKind } from "@/lib/api/freight";
import { useCountries, useProfile } from "@/lib/api/queries";
import {
  INCOTERMS,
  type Incoterm,
  PAYMENT_TERMS,
  type PaymentTerms,
  type QuoteIn,
  useCreateQuote,
  useQuotePreview,
} from "@/lib/api/quotes";
import { capitalize } from "@/lib/format";

const RISK: Record<string, string> = { low: "Low risk", medium: "Some risk", high: "High risk" };

function num(text: string): number | null {
  const n = Number(text.replace(/[$,\s]/g, ""));
  return Number.isFinite(n) && n > 0 ? n : null;
}

function Labeled({
  label,
  children,
  wide = false,
}: {
  label: string;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <label
      className={`flex flex-col gap-1 text-xs font-medium text-muted ${wide ? "sm:col-span-2" : ""}`}
    >
      {label}
      {children}
    </label>
  );
}

/** Build a quote or proforma from the user's numbers, priced live by the server. */
export function QuoteBuilder() {
  const router = useRouter();
  const search = useSearchParams();
  const profile = useProfile();
  const countries = useCountries();
  const create = useCreateQuote();

  const [kind, setKind] = useState<"quote" | "proforma">("quote");
  const [hs6, setHs6] = useState(search.get("hs6") ?? "");
  const [market, setMarket] = useState(search.get("market") ?? "");
  const [buyer, setBuyer] = useState(search.get("buyer") ?? "");
  const [address, setAddress] = useState("");
  const [qty, setQty] = useState(search.get("kg") ?? "");
  const [price, setPrice] = useState(search.get("price") ?? "");
  const [incoterm, setIncoterm] = useState<Incoterm>("CIF");
  const [container, setContainer] = useState<ContainerKind>(
    (search.get("ship") as ContainerKind | null) ?? "40ft",
  );
  const [freight, setFreight] = useState("");
  const [payment, setPayment] = useState<PaymentTerms>("deposit_30");
  const [validity, setValidity] = useState("30");
  const contactId = search.get("contact");

  const products = profile.data?.products ?? [];
  // Default to the user's first product once the profile loads.
  const product = hs6 || products[0]?.hs6 || "";

  const body = useMemo<QuoteIn | null>(() => {
    const quantity = num(qty);
    const unit = num(price);
    if (!product || !market || buyer.trim().length < 2 || !quantity || !unit) return null;
    return {
      kind,
      hs6: product,
      market,
      buyer_name: buyer.trim(),
      buyer_address: address.trim() || null,
      quantity_kg: quantity,
      unit_price_fob: unit,
      incoterm,
      container,
      freight_usd: freight.trim() ? num(freight) : null,
      payment_terms: payment,
      validity_days: Math.min(180, Math.max(1, Number(validity) || 30)),
      contact_id: contactId,
    };
  }, [
    kind,
    product,
    market,
    buyer,
    address,
    qty,
    price,
    incoterm,
    container,
    freight,
    payment,
    validity,
    contactId,
  ]);

  // Re-price after the user pauses typing.
  const [debounced, setDebounced] = useState(body);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(body), 450);
    return () => clearTimeout(t);
  }, [body]);
  const preview = useQuotePreview(debounced);

  if (profile.isPending || countries.isPending)
    return (
      <Page>
        <Skeleton className="h-96" />
      </Page>
    );

  const markets = (countries.data ?? []).filter((c) => c.code !== profile.data?.exporter.code);
  const quote = preview.data;

  return (
    <Page>
      <PageHeader
        title={kind === "proforma" ? "New proforma invoice" : "New quote"}
        description="Priced by Incoterms® 2020 from your FOB price. The buyer sees only the document on the right."
      />
      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
        <Card className="no-print flex flex-col gap-4 p-5">
          <Segmented
            label="Document"
            value={kind}
            onChange={setKind}
            items={[
              { value: "quote", label: "Quote" },
              { value: "proforma", label: "Proforma invoice" },
            ]}
          />
          <div className="grid gap-3 sm:grid-cols-2">
            <Labeled label="Product" wide>
              <select
                value={product}
                onChange={(e) => setHs6(e.target.value)}
                className={`${inputClass} text-sm`}
              >
                {!products.some((p) => p.hs6 === product) && product && (
                  <option value={product}>HS {product}</option>
                )}
                {products.map((p) => (
                  <option key={p.hs6} value={p.hs6}>
                    {capitalize(p.name)} (HS {p.hs6})
                  </option>
                ))}
              </select>
            </Labeled>
            <Labeled label="Buyer’s country" wide>
              <select
                value={market}
                onChange={(e) => setMarket(e.target.value)}
                className={`${inputClass} text-sm`}
              >
                <option value="">Choose…</option>
                {markets.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.name}
                  </option>
                ))}
              </select>
            </Labeled>
            <Labeled label="Buyer (company)" wide>
              <input
                value={buyer}
                onChange={(e) => setBuyer(e.target.value)}
                maxLength={160}
                className={`${inputClass} text-sm`}
              />
            </Labeled>
            <Labeled label="Buyer’s address (optional)" wide>
              <textarea
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                rows={2}
                maxLength={400}
                className={`${inputClass} text-sm`}
              />
            </Labeled>
            <Labeled label="Quantity (kg)">
              <input
                inputMode="decimal"
                value={qty}
                onChange={(e) => setQty(e.target.value)}
                placeholder="9280"
                className={`${inputClass} text-sm tabular-nums`}
              />
            </Labeled>
            <Labeled label="Your price, FOB (US$/kg)">
              <input
                inputMode="decimal"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                placeholder="5.00"
                className={`${inputClass} text-sm tabular-nums`}
              />
            </Labeled>
          </div>

          <div className="flex flex-col gap-2">
            <Segmented
              label="Price basis"
              value={incoterm}
              onChange={setIncoterm}
              items={INCOTERMS}
            />
            <p className="text-xs text-subtle">
              {INCOTERMS.find((i) => i.value === incoterm)?.explain}
            </p>
          </div>
          {incoterm !== "FOB" && (
            <>
              <Segmented
                label="Container"
                value={container}
                onChange={setContainer}
                items={CONTAINER_OPTIONS}
              />
              <Labeled label="Freight from your forwarder (US$, optional)">
                <input
                  inputMode="decimal"
                  value={freight}
                  onChange={(e) => setFreight(e.target.value)}
                  placeholder="Our estimate is used if empty"
                  className={`${inputClass} text-sm tabular-nums`}
                />
              </Labeled>
            </>
          )}
          <div className="grid gap-3 sm:grid-cols-[1fr_7rem]">
            <Labeled label="Payment terms">
              <select
                value={payment}
                onChange={(e) => setPayment(e.target.value as PaymentTerms)}
                className={`${inputClass} text-sm`}
              >
                {PAYMENT_TERMS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </Labeled>
            <Labeled label="Valid (days)">
              <input
                inputMode="numeric"
                value={validity}
                onChange={(e) => setValidity(e.target.value)}
                className={`${inputClass} text-sm tabular-nums`}
              />
            </Labeled>
          </div>
          {quote && (
            <Callout tone={quote.payment.risk === "high" ? "caution" : "neutral"}>
              <span className="block font-medium">{RISK[quote.payment.risk]} for you</span>
              {quote.payment.explain}
            </Callout>
          )}
          {preview.isError && (
            <p role="alert" className="flex gap-2 text-sm text-negative">
              <ShieldAlert className="h-4 w-4 shrink-0" aria-hidden /> {preview.error.message}
            </p>
          )}
          {quote && quote.seller_notes.length > 0 && (
            <ul className="flex flex-col gap-2 rounded-xl bg-surface-2/60 p-3 text-xs leading-5 text-muted">
              {quote.seller_notes.map((n) => (
                <li key={n} className="flex gap-2">
                  <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden /> {n}
                </li>
              ))}
            </ul>
          )}
          <Button
            size="lg"
            disabled={!debounced || !quote || create.isPending || preview.isFetching}
            onClick={() =>
              debounced &&
              create.mutate(debounced, { onSuccess: (q) => router.push(`/app/quotes/${q.id}`) })
            }
          >
            {create.isPending && <LoaderCircle className="animate-spin" />}
            Issue {kind === "proforma" ? "proforma" : "quote"}
          </Button>
          {create.isError && <p className="text-sm text-negative">{create.error.message}</p>}
          <Link
            href="/app/settings/business"
            className="text-xs text-muted underline-offset-4 hover:underline"
          >
            Edit your company details on quotes
          </Link>
        </Card>

        <div
          aria-live="polite"
          className={preview.isFetching ? "opacity-70 transition-opacity" : ""}
        >
          {quote ? (
            <QuoteDocument quote={quote} draft />
          ) : (
            <Card className="flex min-h-80 items-center justify-center p-8 text-center text-sm text-muted">
              Choose the buyer’s country, then enter the buyer, quantity and your FOB price to see
              the quote.
            </Card>
          )}
        </div>
      </div>
    </Page>
  );
}
