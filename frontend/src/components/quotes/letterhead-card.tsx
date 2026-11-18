"use client";

import { FileSignature } from "lucide-react";
import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/empty";
import { Field, inputClass } from "@/components/ui/field";
import { type Business, type BusinessIn, useBusiness, useSaveBusiness } from "@/lib/api/quotes";

const FIELDS: { key: keyof BusinessIn; label: string; hint?: string; max: number }[] = [
  { key: "company_name", label: "Company name", max: 160 },
  { key: "address", label: "Address", hint: "Street, city, country", max: 400 },
  { key: "phone", label: "Phone", max: 40 },
  { key: "email", label: "Email for buyers", max: 320 },
  { key: "website", label: "Website", max: 255 },
  {
    key: "tax_id",
    label: "Tax / export registration",
    hint: "e.g. NTN, VAT or EORI number",
    max: 60,
  },
];

function Form({ business }: { business: Business }) {
  const save = useSaveBusiness();
  const [saved, setSaved] = useState(false);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const body = Object.fromEntries(
      [...FIELDS.map((f) => f.key), "bank_details"].map((k) => [k, String(form.get(k) ?? "")]),
    ) as BusinessIn;
    save.mutate(body, {
      onSuccess: () => {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      },
    });
  }

  return (
    <form onSubmit={onSubmit} className="mt-5 grid gap-4 sm:grid-cols-2">
      {FIELDS.map((f) => (
        <Field
          key={f.key}
          id={f.key}
          name={f.key}
          label={f.label}
          hint={f.hint}
          maxLength={f.max}
          defaultValue={business[f.key] ?? ""}
        />
      ))}
      <label className="flex flex-col gap-1.5 sm:col-span-2" htmlFor="bank_details">
        <span className="text-sm font-medium text-fg">Bank details (printed on proformas)</span>
        <textarea
          id="bank_details"
          name="bank_details"
          rows={3}
          maxLength={600}
          defaultValue={business.bank_details ?? ""}
          placeholder="Bank, account name, IBAN / account number, SWIFT"
          className={`${inputClass} text-base sm:text-sm`}
        />
      </label>
      <div className="flex items-center gap-3 sm:col-span-2">
        <Button type="submit" disabled={save.isPending}>
          Save
        </Button>
        {saved && <span className="pop-in text-sm text-positive">Saved</span>}
        {save.isError && <span className="text-sm text-negative">{save.error.message}</span>}
      </div>
    </form>
  );
}

/** The seller block printed on quotes and proformas. */
export function LetterheadCard() {
  const business = useBusiness();
  return (
    <Card className="p-5 sm:p-6">
      <CardHeader
        icon={<FileSignature />}
        title="On your quotes"
        description="Your company as buyers see it on quotes and proforma invoices."
      />
      {business.data ? <Form business={business.data} /> : <Skeleton className="mt-5 h-48" />}
    </Card>
  );
}
