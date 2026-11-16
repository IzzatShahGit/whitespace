"use client";

import { BookOpen, Search } from "lucide-react";
import { useState } from "react";

import { Card, Page, PageHeader } from "@/components/ui/card";
import { inputClass } from "@/components/ui/field";

type Term = { term: string; plain: string; example?: string };

const SECTIONS: { title: string; terms: Term[] }[] = [
  {
    title: "Products and markets",
    terms: [
      {
        term: "HS code",
        plain:
          "The number customs use to name a product, the same in every country. The first 6 digits are worldwide.",
        example: "630260 = cotton towels. Searching in plain words finds it for you.",
      },
      {
        term: "Market",
        plain: "A country that buys a product from abroad (its imports).",
      },
      {
        term: "Market size",
        plain: "How much a country imported of the product in a year, in US dollars.",
      },
      {
        term: "Growth a year",
        plain:
          "How fast those imports grew each year on average over the last three years. +10% means demand is rising.",
      },
      {
        term: "Your share",
        plain: "Of everything the market imports, the part that comes from your country.",
      },
      {
        term: "Main rival",
        plain:
          "The country that supplies the market the most (besides yours). If its share is falling, buyers may be open to new suppliers.",
      },
      {
        term: "Exports competitively",
        plain:
          "Your country exports more of this product than the world average would suggest (economists call it RCA above 1). We only rank products where this is true.",
      },
    ],
  },
  {
    title: "Our verdicts",
    terms: [
      { term: "Go for it", plain: "Demand is growing and the market is open. Worth pursuing now." },
      { term: "Grow your lead", plain: "Your country is already big here. Build on it." },
      {
        term: "Worth testing",
        plain: "Steady market with no clear winner. Try a small shipment first.",
      },
      {
        term: "Defend your position",
        plain: "You’re established, but a rival is gaining share. Protect your buyers.",
      },
      {
        term: "Approach with care",
        plain: "Imports are shrinking. Only go with a clear advantage.",
      },
      {
        term: "Hard to break in",
        plain: "One supplier holds most of the market and isn’t slipping.",
      },
    ],
  },
  {
    title: "Prices and costs",
    terms: [
      {
        term: "Price per kg",
        plain:
          "Customs value divided by weight: an average across qualities, not a quote. Good for comparing, not for invoicing.",
      },
      {
        term: "FOB (free on board)",
        plain:
          "Your price with the goods loaded on the ship in your country. Freight and insurance are the buyer’s.",
      },
      {
        term: "CIF (cost, insurance, freight)",
        plain:
          "Your price including shipping and insurance to the buyer’s port. Most countries charge duty on this.",
      },
      {
        term: "Landed cost",
        plain: "Price + freight + insurance + import duty: what the buyer really pays per kg.",
      },
      {
        term: "Lakh and crore",
        plain: "1 lakh = 100,000 and 1 crore = 10,000,000. Type amounts this way; we convert them.",
        example: "18 lakh PKR ≈ US$6,500 at today’s rate.",
      },
    ],
  },
  {
    title: "Duties and trade deals",
    terms: [
      {
        term: "Import duty (tariff)",
        plain: "A tax the buying country charges when goods arrive, as a % of their value.",
      },
      {
        term: "Standard rate (MFN)",
        plain: "The duty a country charges everyone without a special deal.",
      },
      {
        term: "Preferential rate",
        plain:
          "A lower duty (often 0%) for countries with a trade deal or a development scheme. You usually need a certificate of origin to claim it.",
      },
      {
        term: "GSP, GSP+, EBA",
        plain:
          "EU schemes that cut duties for developing countries. GSP+ (e.g. Pakistan, Sri Lanka) and Everything But Arms (least developed countries, e.g. Bangladesh, Ethiopia) give 0% on most goods.",
      },
      {
        term: "DCTS",
        plain: "The UK’s version: the Developing Countries Trading Scheme.",
      },
      {
        term: "Certificate of origin",
        plain:
          "A document proving where the goods were made. Your chamber of commerce or export authority issues it; buyers need it to pay the lower duty.",
      },
    ],
  },
];

/** Every term the app uses, in plain words, searchable. */
export function Glossary() {
  const [q, setQ] = useState("");
  const query = q.trim().toLowerCase();
  const sections = SECTIONS.map((s) => ({
    ...s,
    terms: s.terms.filter(
      (t) => !query || `${t.term} ${t.plain} ${t.example ?? ""}`.toLowerCase().includes(query),
    ),
  })).filter((s) => s.terms.length);

  return (
    <Page>
      <PageHeader
        title="Trade terms, simply"
        description="Every word Whitespace uses, explained in plain language. Still stuck? Ask Whitespace in your own language."
      />
      <label className="relative block max-w-md">
        <span className="sr-only">Search terms</span>
        <Search className="pointer-events-none absolute top-1/2 left-3.5 h-4 w-4 -translate-y-1/2 text-subtle" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search, e.g. duty, FOB, lakh"
          className={`${inputClass} pl-10`}
        />
      </label>
      {sections.map((section) => (
        <Card key={section.title} className="rise-in p-5 sm:p-6">
          <h2 className="flex items-center gap-2 text-base font-semibold">
            <BookOpen className="h-4 w-4 text-brand" /> {section.title}
          </h2>
          <dl className="mt-4 grid gap-x-8 gap-y-4 md:grid-cols-2">
            {section.terms.map((t) => (
              <div key={t.term}>
                <dt className="text-sm font-semibold">{t.term}</dt>
                <dd className="mt-0.5 text-sm leading-6 text-muted">{t.plain}</dd>
                {t.example && <dd className="mt-1 text-xs text-subtle">{t.example}</dd>}
              </div>
            ))}
          </dl>
        </Card>
      ))}
      {!sections.length && <p className="text-sm text-muted">No term matches “{q}”.</p>}
    </Page>
  );
}
