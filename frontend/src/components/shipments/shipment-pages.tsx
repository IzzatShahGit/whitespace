"use client";

import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  CircleDashed,
  PackageCheck,
  Printer,
  Ship,
  Trash2,
  Truck,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, use, useState } from "react";

import { CommercialInvoice, OriginDocument, PackingList } from "@/components/shipments/documents";
import { Callout } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, Page, PageHeader } from "@/components/ui/card";
import { EmptyState, Skeleton } from "@/components/ui/empty";
import { inputClass } from "@/components/ui/field";
import { Segmented } from "@/components/ui/segmented";
import { track } from "@/lib/analytics";
import {
  type Shipment,
  type ShipmentDetails,
  useDeleteShipment,
  useShipment,
  useShipments,
  useUpdateShipment,
} from "@/lib/api/shipments";

type Tab = "checklist" | "invoice" | "packing" | "origin";

const STATUS = {
  ready: { icon: CheckCircle2, className: "text-positive", label: "Ready" },
  fill_in: { icon: CircleDashed, className: "text-caution", label: "Fill in" },
  from_others: { icon: Truck, className: "text-muted", label: "From others" },
} as const;

const FIELDS: {
  key: keyof ShipmentDetails;
  label: string;
  type?: "number" | "date" | "area";
  hint?: string;
}[] = [
  { key: "invoice_date", label: "Invoice date", type: "date" },
  { key: "packages", label: "Number of packages", type: "number" },
  { key: "package_type", label: "Package type", hint: "cartons, bales, pallets…" },
  { key: "net_kg", label: "Net weight (kg)", type: "number" },
  { key: "gross_kg", label: "Gross weight (kg)", type: "number" },
  { key: "package_size_cm", label: "Package size (cm)", hint: "60x40x40" },
  { key: "origin_criterion", label: "Origin criterion", hint: "P, or W + HS heading" },
  { key: "vessel", label: "Vessel" },
  { key: "voyage", label: "Voyage" },
  { key: "bl_number", label: "Bill of lading no." },
  { key: "containers", label: "Container no(s)." },
  { key: "seals", label: "Seal no(s)." },
  { key: "final_destination", label: "Final destination" },
  { key: "consignee_address", label: "Buyer’s address", type: "area" },
  { key: "notify_party", label: "Notify party", type: "area" },
  { key: "marks", label: "Shipping marks", type: "area" },
];

function DetailsForm({ s }: { s: Shipment }) {
  const update = useUpdateShipment(s.id);
  const [saved, setSaved] = useState(false);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const body: Record<string, unknown> = { version: s.version };
    for (const f of FIELDS) {
      const raw = String(form.get(f.key) ?? "").trim();
      const before = s.details[f.key];
      const value = f.type === "number" ? (raw ? Number(raw) : null) : raw || null;
      if (value !== (before ?? null))
        body[f.key] = value ?? (f.key === "package_type" ? "cartons" : null);
    }
    update.mutate(body as Parameters<typeof update.mutate>[0], {
      onSuccess: () => {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      },
    });
  }

  return (
    <form key={s.version} onSubmit={onSubmit} className="grid gap-3 sm:grid-cols-3">
      {FIELDS.map((f) => (
        <label
          key={f.key}
          className={`flex flex-col gap-1 text-xs font-medium text-muted ${f.type === "area" ? "sm:col-span-3" : ""}`}
        >
          {f.label}
          {f.type === "area" ? (
            <textarea
              name={f.key}
              rows={2}
              defaultValue={String(s.details[f.key] ?? "")}
              className={`${inputClass} text-sm`}
            />
          ) : (
            <input
              name={f.key}
              type={f.type === "date" ? "date" : "text"}
              inputMode={f.type === "number" ? "decimal" : undefined}
              defaultValue={String(s.details[f.key] ?? "")}
              placeholder={f.hint}
              className={`${inputClass} text-sm`}
            />
          )}
        </label>
      ))}
      <div className="flex items-center gap-3 sm:col-span-3">
        <Button type="submit" disabled={update.isPending}>
          Save details
        </Button>
        {saved && <span className="pop-in text-sm text-positive">Saved</span>}
        {update.isError && <span className="text-sm text-negative">{update.error.message}</span>}
      </div>
    </form>
  );
}

/** One shipment: what's ready, the details to fill in, and the documents to print. */
export function ShipmentView({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const shipment = useShipment(id);
  const remove = useDeleteShipment();
  const [tab, setTab] = useState<Tab>("checklist");

  if (shipment.isPending)
    return (
      <Page>
        <Skeleton className="h-[40rem]" />
      </Page>
    );
  if (!shipment.data) {
    return (
      <Page>
        <EmptyState icon={<Ship />} title="Shipment not found">
          It may have been deleted.
        </EmptyState>
      </Page>
    );
  }
  const s = shipment.data;
  const tabs = [
    { value: "checklist" as Tab, label: "Checklist & details" },
    { value: "invoice" as Tab, label: "Commercial invoice" },
    { value: "packing" as Tab, label: "Packing list" },
    ...(s.origin.kind === "eu_gsp_statement"
      ? [{ value: "origin" as Tab, label: "Statement on origin" }]
      : []),
  ];

  return (
    <Page className="gap-5">
      <div className="no-print flex flex-wrap items-center justify-between gap-3">
        <Link
          href="/app/shipments"
          className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-fg"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden /> All shipments
        </Link>
        <div className="flex gap-2">
          <Button
            variant="ghost"
            onClick={() => {
              if (window.confirm(`Delete the documents for ${s.invoice_number}?`)) {
                remove.mutate(id, { onSuccess: () => router.push("/app/shipments") });
              }
            }}
          >
            <Trash2 /> Delete
          </Button>
          {tab !== "checklist" && (
            <Button
              onClick={() => {
                track("deal_sheet_print");
                window.print();
              }}
            >
              <Printer /> Print / PDF
            </Button>
          )}
        </div>
      </div>
      <div className="no-print">
        <PageHeader
          title={`${s.invoice_number}: ${s.buyer.name}`}
          description={`${s.description} · ${s.quantity_kg.toLocaleString("en")} kg · ${s.incoterm} ${s.named_place}`}
        />
      </div>
      <div className="no-print">
        <Segmented label="Document" value={tab} onChange={setTab} items={tabs} />
      </div>

      {tab === "checklist" && (
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
          <Card className="p-5 sm:p-6">
            <CardHeader icon={<PackageCheck />} title="What this shipment needs" />
            <ul className="mt-5 flex flex-col gap-3">
              {s.checklist.map((item) => {
                const st = STATUS[item.status];
                return (
                  <li key={item.title} className="flex gap-3">
                    <st.icon className={`mt-0.5 h-4 w-4 shrink-0 ${st.className}`} aria-hidden />
                    <span>
                      <span className="block text-sm font-medium">
                        {item.title} <span className={`text-xs ${st.className}`}>· {st.label}</span>
                      </span>
                      <span className="block text-xs leading-5 text-muted">{item.detail}</span>
                    </span>
                  </li>
                );
              })}
            </ul>
            {s.origin.guidance.length > 0 && (
              <div className="mt-6 border-t border-line pt-4 text-xs leading-5 text-muted">
                <p className="mb-1 font-medium text-fg">
                  {s.origin.kind === "eu_gsp_statement"
                    ? "About the statement on origin"
                    : "Proof of origin"}
                </p>
                <ul className="list-disc ps-4">
                  {s.origin.guidance.map((g) => (
                    <li key={g}>{g}</li>
                  ))}
                </ul>
              </div>
            )}
          </Card>
          <Card className="flex flex-col gap-4 p-5 sm:p-6">
            <CardHeader
              icon={<Ship />}
              title="Shipping details"
              description="Printed on the invoice and packing list."
            />
            {s.warnings.length > 0 && (
              <Callout tone="caution">
                <ul className="flex flex-col gap-1">
                  {s.warnings.map((w) => (
                    <li key={w} className="flex gap-2">
                      <AlertTriangle className="mt-1 h-3.5 w-3.5 shrink-0" aria-hidden /> {w}
                    </li>
                  ))}
                </ul>
              </Callout>
            )}
            <DetailsForm s={s} />
          </Card>
        </div>
      )}
      <div className="mx-auto w-full max-w-3xl">
        {tab === "invoice" && <CommercialInvoice s={s} />}
        {tab === "packing" && <PackingList s={s} />}
        {tab === "origin" && <OriginDocument s={s} />}
      </div>
    </Page>
  );
}

/** Every shipment the user has prepared documents for. */
export function ShipmentsList() {
  const shipments = useShipments();
  return (
    <Page>
      <PageHeader
        title="Shipments"
        description="Commercial invoices, packing lists and origin statements for your won deals."
      />
      {shipments.isPending ? (
        <Skeleton className="h-48" />
      ) : !shipments.data?.length ? (
        <Card className="p-6">
          <EmptyState icon={<Ship />} title="No shipments yet">
            Open an issued quote and press “Prepare shipping documents”. We fill in the invoice from
            the quote; you add the packing and transport details.
          </EmptyState>
        </Card>
      ) : (
        <Card className="p-2 sm:p-3">
          <ul className="divide-y divide-line">
            {shipments.data.map((s) => (
              <li key={s.id}>
                <Link
                  href={`/app/shipments/${s.id}`}
                  className="flex items-center justify-between gap-3 rounded-xl px-3 py-3 transition-colors hover:bg-surface-2"
                >
                  <span className="min-w-0">
                    <span className="block truncate font-medium">{s.buyer_name}</span>
                    <span className="text-xs text-muted">
                      {s.invoice_number} · {new Date(s.created_at).toLocaleDateString("en-GB")}
                    </span>
                  </span>
                  <span className="shrink-0 font-medium tabular-nums">
                    US${s.total_usd.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </Page>
  );
}
