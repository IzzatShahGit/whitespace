import type { Quote } from "@/lib/api/quotes";

const money = (n: number) =>
  `US$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const day = (iso: string) =>
  new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });

function PartyBlock({ title, party }: { title: string; party: Quote["seller"] }) {
  return (
    <div className="min-w-0">
      <p className="text-[11px] font-semibold tracking-wide text-neutral-500 uppercase">{title}</p>
      <p className="mt-1 font-semibold">{party.name}</p>
      {party.address && <p className="whitespace-pre-line">{party.address}</p>}
      <p>{party.country}</p>
      {party.phone && <p>{party.phone}</p>}
      {party.email && <p>{party.email}</p>}
      {party.website && <p>{party.website}</p>}
      {party.tax_id && <p>Reg. no. {party.tax_id}</p>}
    </div>
  );
}

/**
 * The document the buyer receives: always black on white (also in dark mode), so the
 * screen preview matches the printed PDF. Seller-only notes are never part of it.
 */
export function QuoteDocument({ quote, draft = false }: { quote: Quote; draft?: boolean }) {
  const title = quote.kind === "proforma" ? "Proforma invoice" : "Quotation";
  return (
    <article className="quote-doc relative rounded-xl border border-neutral-200 bg-white p-6 text-[13px] leading-5 text-neutral-900 shadow-card sm:p-10 print:rounded-none print:border-0 print:p-0 print:shadow-none">
      {draft && (
        <span className="absolute top-4 right-4 rounded bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800 print:hidden">
          Preview
        </span>
      )}
      <header className="flex flex-wrap items-start justify-between gap-4 border-b border-neutral-200 pb-5">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          <p className="mt-1 text-neutral-600">
            {quote.number ?? "No. (on issue)"} · {day(quote.issued)}
          </p>
        </div>
        <div className="text-right text-neutral-600">
          <p>
            Valid until <strong className="text-neutral-900">{day(quote.valid_until)}</strong>
          </p>
          <p>
            {quote.incoterm} {quote.named_place} · Incoterms® 2020
          </p>
        </div>
      </header>

      <section className="grid gap-6 border-b border-neutral-200 py-5 sm:grid-cols-2">
        <PartyBlock title="From" party={quote.seller} />
        <PartyBlock title="To" party={quote.buyer} />
      </section>

      <table className="mt-5 w-full">
        <thead>
          <tr className="border-b border-neutral-300 text-left text-[11px] tracking-wide text-neutral-500 uppercase">
            <th scope="col" className="pb-2 font-semibold">
              Description
            </th>
            <th scope="col" className="pb-2 text-right font-semibold">
              Amount
            </th>
          </tr>
        </thead>
        <tbody>
          {quote.lines.map((line) => (
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
              Total, {quote.incoterm} {quote.named_place}
            </td>
            <td className="pt-3 text-right text-base font-semibold tabular-nums">
              {money(quote.total_usd)}
            </td>
          </tr>
          <tr>
            <td className="text-right text-neutral-600">Price per kg</td>
            <td className="text-right text-neutral-600 tabular-nums">
              US${quote.unit_price_usd_kg.toFixed(2)}
            </td>
          </tr>
        </tfoot>
      </table>

      <section className="mt-6 border-t border-neutral-200 pt-4">
        <p className="text-[11px] font-semibold tracking-wide text-neutral-500 uppercase">Terms</p>
        <ul className="mt-2 flex list-disc flex-col gap-1 pl-5">
          {quote.terms.map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ul>
      </section>

      {quote.kind === "proforma" && quote.bank_details && (
        <section className="mt-5 rounded-lg bg-neutral-50 p-4 print:border print:border-neutral-200">
          <p className="text-[11px] font-semibold tracking-wide text-neutral-500 uppercase">
            Bank details
          </p>
          <p className="mt-1 whitespace-pre-line">{quote.bank_details}</p>
        </section>
      )}
    </article>
  );
}
