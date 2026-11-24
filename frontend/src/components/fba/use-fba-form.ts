"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { replaceSearchParams } from "@/components/markets/url-state";
import type { FbaCategoryKey, FbaInput } from "@/lib/api/fba";

export type UnitSystem = "metric" | "imperial";
export type Shipping = FbaInput["shipping"];

/** The form as typed: strings, so half-typed numbers ("4.") don't jump around. */
export type FbaForm = {
  hs6: string;
  product: string; // display name of the picked product
  origin: string;
  cost: string;
  price: string;
  category: FbaCategoryKey;
  unit: UnitSystem;
  length: string;
  width: string;
  height: string;
  weight: string;
  units: string;
  sales: string;
  ads: string;
  returns: string;
  prep: string;
  usFees: string;
  shipping: Shipping;
  freight: string; // the seller's own freight quote per unit; empty: our estimate
};

/** A worked example (bath towels from Pakistan), so the page opens with a real answer. */
export const EXAMPLE: FbaForm = {
  hs6: "630260",
  product: "Towels and kitchen linen of terry cotton",
  origin: "PAK",
  cost: "4.2",
  price: "29.99",
  category: "home_kitchen",
  unit: "metric",
  length: "35",
  width: "25",
  height: "10",
  weight: "0.7",
  units: "500",
  sales: "150",
  ads: "10",
  returns: "3",
  prep: "0",
  usFees: "450",
  shipping: "auto",
  freight: "",
};

// Short URL names, so a shared link stays readable.
const PARAMS: Record<keyof FbaForm, string> = {
  hs6: "hs6", product: "pn", origin: "from", cost: "cost", price: "price", category: "cat",
  unit: "u", length: "l", width: "w", height: "h", weight: "wt", units: "qty", sales: "sales",
  ads: "ads", returns: "ret", prep: "prep", usFees: "usf", shipping: "ship", freight: "fq",
}; // prettier-ignore

const CATEGORY_KEYS = new Set<string>([
  "home_kitchen", "beauty_health", "baby", "clothing", "footwear", "luggage", "sports", "toys",
  "pet", "grocery", "electronics_accessories", "consumer_electronics", "furniture", "jewelry",
  "other",
]); // prettier-ignore
const SHIPPING = new Set<string>(["auto", "lcl", "20ft", "40ft"]);

const CM_PER_IN = 2.54;
const LB_PER_KG = 2.20462;

function fromUrl(search: URLSearchParams): FbaForm {
  const form = { ...EXAMPLE };
  for (const [field, param] of Object.entries(PARAMS) as [keyof FbaForm, string][]) {
    const value = search.get(param);
    if (value === null || value.length > 120) continue;
    if (field === "category" && !CATEGORY_KEYS.has(value)) continue;
    if (field === "shipping" && !SHIPPING.has(value)) continue;
    if (field === "unit" && value !== "metric" && value !== "imperial") continue;
    (form as Record<string, string>)[field] = value;
  }
  return form;
}

/** The form, kept in the URL (only what differs from the example) so links share it. */
export function useFbaForm() {
  const search = useSearchParams();
  const [form, setForm] = useState<FbaForm>(() => fromUrl(new URLSearchParams(search)));

  function update(changes: Partial<FbaForm>) {
    const next = { ...form, ...changes };
    const params: Record<string, string | null> = {};
    for (const field of Object.keys(changes) as (keyof FbaForm)[]) {
      params[PARAMS[field]] = next[field] === EXAMPLE[field] ? null : next[field];
    }
    setForm(next);
    replaceSearchParams(params);
  }

  /** Switch inches/pounds and cm/kg, converting what's typed. */
  function setUnit(unit: UnitSystem) {
    if (unit === form.unit) return;
    const length = unit === "metric" ? CM_PER_IN : 1 / CM_PER_IN;
    const mass = unit === "metric" ? 1 / LB_PER_KG : LB_PER_KG;
    const convert = (text: string, factor: number) => {
      const n = number(text);
      return n === null ? text : String(Number((n * factor).toFixed(2)));
    };
    update({
      unit,
      length: convert(form.length, length),
      width: convert(form.width, length),
      height: convert(form.height, length),
      weight: convert(form.weight, mass),
    });
  }

  return { form, update, setUnit, reset: () => update({ ...EXAMPLE }) };
}

/** "4.2" -> 4.2; "", "abc", "-1" -> null. Commas as thousands separators are fine. */
export function number(text: string): number | null {
  const n = Number(text.replace(/,/g, "").trim());
  return text.trim() !== "" && Number.isFinite(n) && n >= 0 ? n : null;
}

export type FormErrors = Partial<Record<keyof FbaForm, string>>;

/** The API body, or the fields that stop us asking (keys of the i18n `fba.errors`). */
export function toInput(form: FbaForm): { input: FbaInput | null; errors: FormErrors } {
  const errors: FormErrors = {};
  const positive = (field: keyof FbaForm, max: number) => {
    const n = number(form[field]);
    if (n === null || n <= 0) errors[field] = "required";
    else if (n > max) errors[field] = "tooBig";
    return n ?? 0;
  };
  const optional = (field: keyof FbaForm, max: number, fallback: number) => {
    if (form[field].trim() === "") return fallback;
    const n = number(form[field]);
    if (n === null) errors[field] = "number";
    else if (n > max) errors[field] = "tooBig";
    return n ?? fallback;
  };
  const metric = form.unit === "metric";
  const toIn = (cm: number) => (metric ? cm / CM_PER_IN : cm);
  const body: FbaInput = {
    hs6: form.hs6,
    origin: form.origin,
    unit_cost_usd: positive("cost", 10_000),
    price_usd: positive("price", 10_000),
    category: form.category,
    length_in: toIn(positive("length", metric ? 300 : 120)),
    width_in: toIn(positive("width", metric ? 300 : 120)),
    height_in: toIn(positive("height", metric ? 300 : 120)),
    weight_lb: (metric ? LB_PER_KG : 1) * positive("weight", metric ? 68 : 150),
    units: Math.round(positive("units", 100_000)),
    monthly_sales: Math.round(positive("sales", 100_000)),
    ad_pct: optional("ads", 60, 10),
    return_pct: optional("returns", 60, 3),
    prep_usd: optional("prep", 100, 0),
    us_shipment_fees_usd: optional("usFees", 20_000, 450),
    shipping: form.shipping,
    freight_per_unit_usd: form.freight.trim() === "" ? null : optional("freight", 1_000, 0),
  };
  if (!/^\d{6}$/.test(form.hs6)) errors.hs6 = "required";
  if (!/^[A-Z]{3}$/.test(form.origin)) errors.origin = "required";
  return { input: Object.keys(errors).length ? null : body, errors };
}
