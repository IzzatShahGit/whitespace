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
import { useT } from "@/lib/i18n";
import type { MessageKey } from "@/lib/i18n/en";

const RISK: Record<string, MessageKey> = {
  low: "quotes.riskLow",
  medium: "quotes.riskMedium",
  high: "quotes.riskHigh",
};

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
  const t = useT();
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
        title={kind === "proforma" ? t("quotes.newProforma") : t("quotes.new")}
        description={t("quotes.builderDesc")}
      />
      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
        <Card className="no-print flex flex-col gap-4 p-5">
          <Segmented
            label="Document"
            value={kind}
            onChange={setKind}
            items={[
              { value: "quote", label: t("quotes.quote") },
              { value: "proforma", label: t("quotes.proforma") },
            ]}
          />
          <div className="grid gap-3 sm:grid-cols-2">
            <Labeled label={t("quotes.product")} wide>
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
            <Labeled label={t("quotes.buyerCountry")} wide>
              <select
                value={market}
                onChange={(e) => setMarket(e.target.value)}
                className={`${inputClass} text-sm`}
              >
                <option value="">{t("quotes.choose")}</option>
                {markets.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.name}
                  </option>
                ))}
              </select>
            </Labeled>
            <Labeled label={t("quotes.buyer")} wide>
              <input
                value={buyer}
                onChange={(e) => setBuyer(e.target.value)}
                maxLength={160}
                className={`${inputClass} text-sm`}
              />
            </Labeled>
            <Labeled label={t("quotes.buyerAddress")} wide>
              <textarea
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                rows={2}
                maxLength={400}
                className={`${inputClass} text-sm`}
              />
            </Labeled>
            <Labeled label={t("quotes.quantity")}>
              <input
                inputMode="decimal"
                value={qty}
                onChange={(e) => setQty(e.target.value)}
                placeholder="9280"
                className={`${inputClass} text-sm tabular-nums`}
              />
            </Labeled>
            <Labeled label={t("quotes.price")}>
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
              label={t("quotes.basis")}
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
                label={t("quotes.container")}
                value={container}
                onChange={setContainer}
                items={CONTAINER_OPTIONS}
              />
              <Labeled label={t("quotes.freight")}>
                <input
                  inputMode="decimal"
                  value={freight}
                  onChange={(e) => setFreight(e.target.value)}
                  placeholder={t("quotes.freightPlaceholder")}
                  className={`${inputClass} text-sm tabular-nums`}
                />
              </Labeled>
            </>
          )}
          <div className="grid gap-3 sm:grid-cols-[1fr_7rem]">
            <Labeled label={t("quotes.payment")}>
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
            <Labeled label={t("quotes.validity")}>
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
              <span className="block font-medium">{t(RISK[quote.payment.risk]!)}</span>
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
            {kind === "proforma" ? t("quotes.issueProforma") : t("quotes.issue")}
          </Button>
          {create.isError && <p className="text-sm text-negative">{create.error.message}</p>}
          <Link
            href="/app/settings/business"
            className="text-xs text-muted underline-offset-4 hover:underline"
          >
            {t("quotes.editCompany")}
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
              {t("quotes.previewEmpty")}
            </Card>
          )}
        </div>
      </div>
    </Page>
  );
}
