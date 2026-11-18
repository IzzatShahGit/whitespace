import type { ReactNode } from "react";

import type { Shipment } from "@/lib/api/shipments";

const money = (n: number) =>
  `US$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const kg = (n: number | null | undefined) =>
  n ? `${n.toLocaleString("en-US", { maximumFractionDigits: 2 })} kg` : "—";
const day = (iso: string | null | undefined) =>
  iso
    ? new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-GB", {
        day: "numeric",
        month: "long",
        year: "numeric",
        timeZone: "UTC",
      })
    : "—";

function Paper({
  title,
  number,
  children,
}: {
  title: string;
  number: string;
  children: ReactNode;
}) {
  return (
    <article
      lang="en"
      dir="ltr"
      className="rounded-xl border border-neutral-200 bg-white p-6 text-[13px] leading-5 text-neutral-900 shadow-card sm:p-10 print:rounded-none print:border-0 print:p-0 print:shadow-none"
    >
      <header className="flex flex-wrap items-start justify-between gap-4 border-b border-neutral-200 pb-4">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="text-right text-neutral-600">{number}</p>
      </header>
      {children}
    </article>
  );
}

function Label({ children }: { children: ReactNode }) {
  return (
    <p className="text-[11px] font-semibold tracking-wide text-neutral-500 uppercase">{children}</p>
  );
}

function Parties({ s }: { s: Shipment }) {
  const d = s.details;
  return (
    <section className="grid gap-5 border-b border-neutral-200 py-4 sm:grid-cols-3">
      <div>
        <Label>Exporter</Label>
        <p className="mt-1 font-semibold">{s.seller.name}</p>
        {s.seller.address && <p className="whitespace-pre-line">{s.seller.address}</p>}
        <p>{s.seller.country}</p>
        {s.seller.tax_id && <p>Reg. no. {s.seller.tax_id}</p>}
      </div>
      <div>
        <Label>Consignee</Label>
        <p className="mt-1 font-semibold">{s.buyer.name}</p>
        {s.buyer.address && <p className="whitespace-pre-line">{s.buyer.address}</p>}
        <p>{s.buyer.country}</p>
      </div>
      <div>
        <Label>Notify party</Label>
        <p className="mt-1 whitespace-pre-line">{d.notify_party || "Same as consignee"}</p>
      </div>
    </section>
  );
}

function Transport({ s }: { s: Shipment }) {
  const d = s.details;
  const rows: [string, string][] = [
    ["Port of loading", s.origin_port],
    ["Port of discharge", s.dest_port],
    ["Final destination", d.final_destination || s.buyer.country],
    ["Vessel / voyage", [d.vessel, d.voyage].filter(Boolean).join(" / ") || "—"],
    ["Bill of lading", d.bl_number || "—"],
    ["Container(s)", d.containers || "—"],
    ["Country of origin", s.origin_country],
    ["Terms of delivery", `${s.incoterm} ${s.named_place} (Incoterms® 2020)`],
  ];
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-1.5 border-b border-neutral-200 py-4 sm:grid-cols-4">
      {rows.map(([k, v]) => (
        <div key={k}>
          <dt className="text-[11px] text-neutral-500">{k}</dt>
          <dd className="font-medium">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export function CommercialInvoice({ s }: { s: Shipment }) {
  return (
    <Paper
      title="Commercial invoice"
      number={`${s.invoice_number} · ${day(s.details.invoice_date)}`}
    >
      <Parties s={s} />
      <Transport s={s} />
      <table className="mt-4 w-full">
        <thead>
          <tr className="border-b border-neutral-300 text-left text-[11px] tracking-wide text-neutral-500 uppercase">
            <th scope="col" className="pb-2 font-semibold">
              Description of goods
            </th>
            <th scope="col" className="pb-2 text-right font-semibold">
              Amount
            </th>
          </tr>
        </thead>
        <tbody>
          {s.lines.map((line) => (
            <tr key={line.label} className="border-b border-neutral-100 align-top">
              <td className="py-2.5 pr-4">
                <p className="font-medium">{line.label}</p>
                {line.detail && <p className="text-neutral-600">{line.detail}</p>}
              </td>
              <td className="py-2.5 text-right tabular-nums">{money(line.amount_usd)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td className="pt-3 text-right font-semibold">
              Total, {s.incoterm} {s.named_place}
            </td>
            <td className="pt-3 text-right text-base font-semibold tabular-nums">
              {money(s.total_usd)}
            </td>
          </tr>
        </tfoot>
      </table>
      <section className="mt-5 grid gap-4 border-t border-neutral-200 pt-4 sm:grid-cols-2">
        <div>
          <Label>Packing</Label>
          <p className="mt-1">
            {s.details.packages ? `${s.details.packages} ${s.details.package_type}` : "—"} · Net{" "}
            {kg(s.details.net_kg)} · Gross {kg(s.details.gross_kg)}
          </p>
          {s.details.marks && <p className="whitespace-pre-line">Marks: {s.details.marks}</p>}
        </div>
        <div>
          <Label>Payment</Label>
          <p className="mt-1">{s.payment_text}</p>
          {s.bank_details && (
            <p className="mt-1 whitespace-pre-line text-neutral-600">{s.bank_details}</p>
          )}
        </div>
      </section>
      {s.origin.kind === "eu_gsp_statement" && s.origin.text && (
        <section className="mt-5 border-t border-neutral-200 pt-4">
          <Label>Statement on origin</Label>
          <p className="mt-1 italic">{s.origin.text}</p>
        </section>
      )}
      <p className="mt-6 text-neutral-600">
        We certify that this invoice is true and correct, and that the goods described are of{" "}
        {s.origin_country} origin.
      </p>
      <Signature s={s} />
    </Paper>
  );
}

export function PackingList({ s }: { s: Shipment }) {
  const d = s.details;
  const perNet = d.packages && d.net_kg ? d.net_kg / d.packages : null;
  const perGross = d.packages && d.gross_kg ? d.gross_kg / d.packages : null;
  return (
    <Paper title="Packing list" number={`For invoice ${s.invoice_number} · ${day(d.invoice_date)}`}>
      <Parties s={s} />
      <Transport s={s} />
      <table className="mt-4 w-full">
        <thead>
          <tr className="border-b border-neutral-300 text-left text-[11px] tracking-wide text-neutral-500 uppercase">
            <th scope="col" className="pb-2 font-semibold">
              Goods
            </th>
            <th scope="col" className="pb-2 text-right font-semibold">
              Packages
            </th>
            <th scope="col" className="pb-2 text-right font-semibold">
              Net weight
            </th>
            <th scope="col" className="pb-2 text-right font-semibold">
              Gross weight
            </th>
          </tr>
        </thead>
        <tbody>
          <tr className="border-b border-neutral-100 align-top">
            <td className="py-2.5 pr-4">
              <p className="font-medium">{s.description}</p>
              <p className="text-neutral-600">HS {s.hs6}</p>
              {d.package_size_cm && (
                <p className="text-neutral-600">Package size {d.package_size_cm} cm</p>
              )}
            </td>
            <td className="py-2.5 text-right tabular-nums">
              {d.packages ? `${d.packages} ${d.package_type}` : "—"}
            </td>
            <td className="py-2.5 text-right tabular-nums">{kg(d.net_kg)}</td>
            <td className="py-2.5 text-right tabular-nums">{kg(d.gross_kg)}</td>
          </tr>
        </tbody>
      </table>
      <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {(
          [
            ["Per package, net", perNet ? kg(perNet) : "—"],
            ["Per package, gross", perGross ? kg(perGross) : "—"],
            ["Total volume", s.volume_m3 ? `${s.volume_m3} m³` : "—"],
            ["Seal(s)", d.seals || "—"],
          ] as const
        ).map(([k, v]) => (
          <div key={k}>
            <dt className="text-[11px] text-neutral-500">{k}</dt>
            <dd className="font-medium tabular-nums">{v}</dd>
          </div>
        ))}
      </dl>
      {d.marks && (
        <section className="mt-4 border-t border-neutral-200 pt-4">
          <Label>Shipping marks</Label>
          <p className="mt-1 whitespace-pre-line">{d.marks}</p>
        </section>
      )}
      <Signature s={s} />
    </Paper>
  );
}

export function OriginDocument({ s }: { s: Shipment }) {
  if (s.origin.kind !== "eu_gsp_statement" || !s.origin.text) return null;
  return (
    <Paper title="Statement on origin" number={`Invoice ${s.invoice_number}`}>
      <p className="mt-5 text-neutral-600">
        For the products covered by commercial invoice {s.invoice_number} of{" "}
        {day(s.details.invoice_date)}, consigned to {s.buyer.name}, {s.buyer.country}.
      </p>
      <p className="mt-4 text-[15px] leading-7 italic">{s.origin.text}</p>
      <Signature s={s} />
    </Paper>
  );
}

function Signature({ s }: { s: Shipment }) {
  return (
    <div className="mt-10 grid gap-6 sm:grid-cols-2">
      <div>
        <div className="h-10 border-b border-neutral-400" />
        <p className="mt-1 text-neutral-600">Place and date</p>
      </div>
      <div>
        <div className="h-10 border-b border-neutral-400" />
        <p className="mt-1 text-neutral-600">Signature, {s.seller.name}</p>
      </div>
    </div>
  );
}
