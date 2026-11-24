"use client";

import { Check, Link2, PackageCheck, RotateCcw, Sparkles } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useId, useState } from "react";

import { FbaCosts, FbaDemand, FbaShipment, FbaSummary } from "@/components/fba/fba-results";
import {
  EXAMPLE,
  type FbaForm,
  type FormErrors,
  type Shipping,
  number,
  toInput,
  useFbaForm,
} from "@/components/fba/use-fba-form";
import { ProductPicker } from "@/components/markets/product-picker";
import { Callout } from "@/components/ui/badge";
import { Button, buttonClass } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/empty";
import { Field, inputClass } from "@/components/ui/field";
import { Segmented } from "@/components/ui/segmented";
import { type FbaOptions, useFbaEstimate, useFbaOptions } from "@/lib/api/fba";
import { ApiError, useSourcing } from "@/lib/api/queries";
import { capitalize, shortProductName } from "@/lib/format";
import { useT } from "@/lib/i18n";
import type { MessageKey } from "@/lib/i18n/en";
import { usd } from "@/lib/money";
import { useDebounced } from "@/lib/use-debounced";

const KG_PER_LB = 0.453592;

/**
 * The Amazon FBA calculator: inputs on the left, the answer on the right. Signed out
 * (the free landing page) it uses the public endpoints and invites a sign-up where the
 * signed-in page shows US demand.
 */
export function FbaCalculator({ signedOut = false }: { signedOut?: boolean }) {
  const t = useT();
  const { form, update, setUnit, reset } = useFbaForm();
  const options = useFbaOptions();
  const { input, errors } = toInput(form);
  const settled = useDebounced(input, 450);
  const estimate = useFbaEstimate(settled, { signedOut });
  const isExample = (Object.keys(EXAMPLE) as (keyof FbaForm)[]).every(
    (k) => form[k] === EXAMPLE[k],
  );

  return (
    <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,25rem)_minmax(0,1fr)] xl:gap-8">
      <div className="flex flex-col gap-4 lg:sticky lg:top-6">
        {isExample ? (
          <Callout tone="brand">
            <span className="flex items-start gap-2">
              <Sparkles className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              {t("fba.example")}
            </span>
          </Callout>
        ) : (
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" size="sm" onClick={reset}>
              <RotateCcw className="h-4 w-4" aria-hidden /> {t("fba.reset")}
            </Button>
            <CopyLink />
          </div>
        )}
        <FormCard
          form={form}
          errors={errors}
          update={update}
          setUnit={setUnit}
          options={options.data}
          signedOut={signedOut}
        />
      </div>

      <div className="flex min-w-0 flex-col gap-6" aria-live="polite">
        {input === null ? (
          <Callout tone="caution">{t("fba.result.fixFields")}</Callout>
        ) : estimate.isError ? (
          <Callout tone="negative">
            <p className="font-medium">{t("fba.result.failed")}</p>
            <p className="mt-1 text-sm">
              {estimate.error instanceof ApiError ? estimate.error.message : null}
            </p>
          </Callout>
        ) : !estimate.data ? (
          <>
            <Skeleton className="h-28" />
            <Skeleton className="h-36" />
            <Skeleton className="h-80" />
          </>
        ) : (
          <div
            className={`flex flex-col gap-6 transition-opacity ${
              estimate.isFetching ? "opacity-60" : ""
            }`}
          >
            <FbaSummary data={estimate.data} />
            <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
              <FbaCosts
                data={estimate.data}
                price={settled?.price_usd ?? 0}
                sales={settled?.monthly_sales ?? 0}
                plan={options.data?.plan_usd ?? 0}
              />
              <div className="flex flex-col gap-6">
                <FbaShipment data={estimate.data} />
                {signedOut ? (
                  <SignUpCard />
                ) : (
                  <FbaDemand
                    origin={estimate.data.origin.code}
                    originName={estimate.data.origin.name}
                    hs6={estimate.data.product.hs6}
                  />
                )}
              </div>
            </div>
            <Assumptions notes={estimate.data.notes} asOf={estimate.data.fees_as_of} />
          </div>
        )}
      </div>
    </div>
  );
}

type Update = (changes: Partial<FbaForm>) => void;

function FormCard({
  form,
  errors,
  update,
  setUnit,
  options,
  signedOut,
}: {
  form: FbaForm;
  errors: FormErrors;
  update: Update;
  setUnit: (unit: FbaForm["unit"]) => void;
  options: FbaOptions | undefined;
  signedOut: boolean;
}) {
  const t = useT();
  const id = useId();
  const [picking, setPicking] = useState(false);
  const err = (field: keyof FbaForm) =>
    errors[field] ? t(`fba.errors.${errors[field]}` as MessageKey) : undefined;
  const metric = form.unit === "metric";
  const num = (field: keyof FbaForm, label: string, extra: Partial<FieldProps> = {}) => (
    <Field
      id={`${id}-${field}`}
      label={label}
      inputMode="decimal"
      autoComplete="off"
      value={form[field]}
      onChange={(e) => update({ [field]: e.target.value })}
      error={err(field)}
      {...extra}
    />
  );

  return (
    <Card className="flex flex-col gap-6 p-4 sm:p-6">
      <CardHeader icon={<PackageCheck />} title={t("fba.sections.product")} />
      <section className="-mt-3 flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-medium" id={`${id}-product-label`}>
            {t("fba.fields.product")}
          </span>
          {picking || !form.hs6 ? (
            <ProductPicker
              mode={signedOut ? "public" : "buy"}
              exporter={undefined}
              id={`${id}-product`}
              label={t("fba.fields.product")}
              placeholder={t("fba.fields.productPlaceholder")}
              autoFocus={picking}
              onSelect={(p) => {
                update({
                  hs6: p.hs6,
                  product: capitalize(p.name ?? shortProductName(p.description)),
                });
                setPicking(false);
              }}
            />
          ) : (
            <div className="flex items-center justify-between gap-3 rounded-xl border border-line bg-surface-2/60 px-4 py-2.5">
              <span className="min-w-0 truncate text-sm">
                {form.product}{" "}
                <span className="text-xs text-subtle tabular-nums">HS {form.hs6}</span>
              </span>
              <button
                type="button"
                className="shrink-0 text-sm font-medium text-brand hover:underline"
                onClick={() => setPicking(true)}
              >
                {t("fba.fields.change")}
              </button>
            </div>
          )}
          {err("hs6") && <p className="text-xs text-negative">{err("hs6")}</p>}
        </div>
        <Select
          id={`${id}-category`}
          label={t("fba.fields.category")}
          value={form.category}
          onChange={(value) => update({ category: value as FbaForm["category"] })}
          options={(options?.categories ?? []).map((c) => ({ value: c.key, label: c.label }))}
        />
      </section>

      <Section title={t("fba.sections.buying")}>
        <Select
          id={`${id}-origin`}
          label={t("fba.fields.origin")}
          value={form.origin}
          onChange={(origin) => update({ origin })}
          options={(options?.origins ?? []).map((c) => ({ value: c.code, label: c.name }))}
          error={err("origin")}
        />
        {num("cost", t("fba.fields.cost"), { hint: t("fba.fields.costHint") })}
        {!signedOut && <TypicalPrice form={form} />}
      </Section>

      <Section title={t("fba.sections.selling")}>
        <div className="grid grid-cols-2 gap-3">
          {num("price", t("fba.fields.price"))}
          {num("sales", t("fba.fields.sales"), { inputMode: "numeric" })}
        </div>
        <p className="-mt-2 text-xs text-subtle">{t("fba.fields.salesHint")}</p>
        {num("units", t("fba.fields.units"), { inputMode: "numeric" })}
      </Section>

      <Section
        title={t("fba.sections.size")}
        action={
          <Segmented
            label={t("fba.fields.unitSystem")}
            value={form.unit}
            onChange={setUnit}
            items={[
              { value: "metric", label: "cm · kg" },
              { value: "imperial", label: "in · lb" },
            ]}
          />
        }
      >
        <div className="grid grid-cols-3 gap-3">
          {num("length", `${t("fba.fields.length")} (${metric ? "cm" : "in"})`)}
          {num("width", `${t("fba.fields.width")} (${metric ? "cm" : "in"})`)}
          {num("height", `${t("fba.fields.height")} (${metric ? "cm" : "in"})`)}
        </div>
        {num("weight", `${t("fba.fields.weight")} (${metric ? "kg" : "lb"})`, {
          hint: t("fba.fields.sizeHint"),
        })}
      </Section>

      <details className="group rounded-xl border border-line px-4 py-3">
        <summary className="cursor-pointer text-sm font-medium select-none">
          {t("fba.sections.more")}
        </summary>
        <div className="mt-4 flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3">
            {num("ads", t("fba.fields.ads"))}
            {num("returns", t("fba.fields.returns"))}
          </div>
          <p className="-mt-2 text-xs text-subtle">{t("fba.fields.adsHint")}</p>
          {num("usFees", t("fba.fields.usFees"), { hint: t("fba.fields.usFeesHint") })}
          {num("prep", t("fba.fields.prep"))}
          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-medium">{t("fba.fields.shipping")}</span>
            <Segmented<Shipping>
              label={t("fba.fields.shipping")}
              value={form.shipping}
              onChange={(shipping) => update({ shipping })}
              items={[
                { value: "auto", label: t("fba.ship.auto") },
                { value: "lcl", label: t("fba.ship.lcl") },
                { value: "20ft", label: t("fba.ship.ft20") },
                { value: "40ft", label: t("fba.ship.ft40") },
              ]}
            />
          </div>
          {num("freight", t("fba.fields.freight"), {
            hint: t("fba.fields.freightHint"),
            placeholder: "—",
          })}
        </div>
      </details>
    </Card>
  );
}

type FieldProps = {
  hint: string;
  inputMode: "decimal" | "numeric";
  placeholder: string;
};

function Section({
  title,
  action,
  children,
}: {
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-4 border-t border-line pt-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold tracking-tight">{title}</h3>
        {action}
      </div>
      {children}
    </section>
  );
}

function Select({
  id,
  label,
  value,
  onChange,
  options,
  error,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  error?: string;
}) {
  const known = options.some((o) => o.value === value);
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={Boolean(error) || undefined}
        className={`${inputClass} appearance-none bg-[length:1rem] pe-10`}
      >
        {!known && <option value={value}>{value || "—"}</option>}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      {error && <p className="text-xs text-negative">{error}</p>}
    </div>
  );
}

/** "Exporters in Pakistan average $3.10/kg: about $2.17 a unit at your weight." */
function TypicalPrice({ form }: { form: FbaForm }) {
  const t = useT();
  const sourcing = useSourcing(form.hs6 ? "USA" : undefined, form.hs6);
  const supplier = sourcing.data?.suppliers.find((s) => s.country.code === form.origin);
  const perKg = supplier?.unit_price_usd_kg;
  const w = number(form.weight);
  if (!supplier || !perKg || !w) return null;
  const kg = form.unit === "metric" ? w : w * KG_PER_LB;
  return (
    <p className="-mt-2 rounded-lg bg-surface-2/70 px-3 py-2 text-xs text-muted">
      {t("fba.fields.typicalPrice", {
        country: supplier.country.name,
        perKg: `${usd(perKg)}/kg`,
        unit: usd(perKg * kg),
      })}
    </p>
  );
}

function CopyLink() {
  const t = useT();
  const [copied, setCopied] = useState(false);
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => {
        void navigator.clipboard?.writeText(window.location.href).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        });
      }}
    >
      {copied ? (
        <Check className="h-4 w-4" aria-hidden />
      ) : (
        <Link2 className="h-4 w-4" aria-hidden />
      )}
      {copied ? t("fba.copied") : t("fba.copyLink")}
    </Button>
  );
}

function SignUpCard() {
  const t = useT();
  const search = useSearchParams(); // carry the inputs into the app after sign-up
  const next = `/app/fba${search.size ? `?${search.toString()}` : ""}`;
  return (
    <Card className="border-brand/30 bg-brand-soft/40 p-4 sm:p-6">
      <h3 className="text-base font-semibold tracking-tight">{t("fba.signup.title")}</h3>
      <p className="mt-1.5 text-sm text-muted">{t("fba.signup.body")}</p>
      <Link
        href={`/signup?next=${encodeURIComponent(next)}`}
        className={`${buttonClass("primary")} mt-4`}
      >
        {t("fba.signup.cta")}
      </Link>
    </Card>
  );
}

function Assumptions({ notes, asOf }: { notes: string[]; asOf: string }) {
  const t = useT();
  return (
    <details className="rounded-2xl border border-line bg-surface px-4 py-3 text-sm sm:px-6">
      <summary className="cursor-pointer font-medium select-none">
        {t("fba.result.assumptions")}
      </summary>
      <ul className="mt-3 flex list-disc flex-col gap-1.5 ps-5 text-muted">
        {notes.map((note) => (
          <li key={note}>{note}</li>
        ))}
        <li>{t("fba.result.feesAsOf", { date: asOf })}</li>
      </ul>
    </details>
  );
}
