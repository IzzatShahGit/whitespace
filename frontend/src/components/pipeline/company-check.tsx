"use client";

import { BadgeCheck, CircleAlert, ExternalLink, HelpCircle, ShieldCheck } from "lucide-react";
import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { inputClass } from "@/components/ui/field";
import { EU, useCompanyCheck, useVatCheck } from "@/lib/api/tenders";
import { useT } from "@/lib/i18n";

/**
 * Is this company registered? Looks the name up in GLEIF (legal entities) and, for EU
 * companies, checks a VAT number with VIES. Confirms registration, not payment record.
 */
export function CompanyCheckBox({ name, country }: { name: string; country: string }) {
  const t = useT();
  const check = useCompanyCheck();
  const vat = useVatCheck();
  const [number, setNumber] = useState("");
  const result = check.data;
  const best = result?.matches[0];

  function onVat(event: FormEvent) {
    event.preventDefault();
    if (number.trim().length >= 4) vat.mutate({ country, number: number.trim() });
  }

  return (
    <div className="flex flex-col gap-2 rounded-xl bg-surface-2/50 p-3 text-xs leading-5">
      {!result && (
        <Button
          size="sm"
          variant="secondary"
          className="self-start"
          disabled={check.isPending}
          onClick={() => check.mutate({ name, country })}
        >
          <ShieldCheck /> {check.isPending ? t("pipeline.checking") : t("pipeline.checkRegister")}
        </Button>
      )}
      {check.isError && <p className="text-negative">{check.error.message}</p>}
      {result && !result.available && (
        <p className="flex gap-1.5 text-muted">
          <CircleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden /> The register isn’t
          answering right now. Try again later.
        </p>
      )}
      {result?.available && best?.exact && (
        <p className={`flex gap-1.5 ${best.active ? "text-positive" : "text-caution"}`}>
          <BadgeCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          <span>
            <strong>{best.name}</strong> is{" "}
            {best.active ? "a registered, active" : "a registered but inactive"} company
            {best.city ? ` in ${best.city}` : ""}
            {best.registered_as ? ` (reg. ${best.registered_as})` : ""}.{" "}
            <a href={best.url} target="_blank" rel="noopener noreferrer" className="underline">
              GLEIF record <ExternalLink className="inline h-3 w-3" aria-hidden />
            </a>
          </span>
        </p>
      )}
      {result?.available && !best?.exact && (
        <div className="flex gap-1.5 text-muted">
          <HelpCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          <span>
            No exact match in the global register of legal entities. That’s common for smaller
            firms; check the legal notice (imprint) on their website instead.
            {result.matches.length > 0 && (
              <>
                {" "}
                Similar names:{" "}
                {result.matches.map((m, i) => (
                  <span key={m.lei}>
                    {i > 0 && "; "}
                    <a href={m.url} target="_blank" rel="noopener noreferrer" className="underline">
                      {m.name}
                    </a>
                    {m.city && ` (${m.city}${m.active ? "" : ", inactive"})`}
                  </span>
                ))}
                .
              </>
            )}
          </span>
        </div>
      )}
      {EU.has(country) && (
        <form onSubmit={onVat} className="flex flex-wrap items-center gap-2">
          <input
            value={number}
            onChange={(e) => setNumber(e.target.value)}
            placeholder="EU VAT number (from their website)"
            aria-label="EU VAT number"
            maxLength={20}
            className={`${inputClass} h-8 w-60 py-0 text-xs`}
          />
          <Button size="sm" variant="ghost" type="submit" disabled={vat.isPending}>
            {t("pipeline.checkVat")}
          </Button>
          {vat.data && (
            <span className={vat.data.valid ? "text-positive" : "text-negative"}>
              {vat.data.number}: {vat.data.valid ? "valid" : "not valid"}
              {vat.data.name ? ` · ${vat.data.name}` : ""}
            </span>
          )}
          {vat.isError && <span className="text-negative">{vat.error.message}</span>}
        </form>
      )}
    </div>
  );
}
