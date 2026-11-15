"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { CountryMultiSelect } from "@/components/markets/country-multi-select";
import { ProductPicker } from "@/components/markets/product-picker";
import { Button } from "@/components/ui/button";
import {
  type Country,
  type Goal,
  type Product,
  type Profile,
  type Role,
  useCountries,
  useExporters,
  useProfile,
  useSaveProfile,
} from "@/lib/api/queries";
import { shortProductName } from "@/lib/format";

const MAX_PRODUCTS = 5;
const GOALS: { value: Goal; label: string; hint: string }[] = [
  { value: "sell", label: "Sell abroad", hint: "Find markets for what I make or stock" },
  { value: "buy", label: "Buy from abroad", hint: "Find the best countries to source from" },
  { value: "both", label: "Both", hint: "I export, and I import inputs" },
];
const ROLES: { value: Role; label: string; hint: string }[] = [
  { value: "exporter", label: "Exporter", hint: "I sell my own products abroad" },
  { value: "consultant", label: "Consultant", hint: "I advise exporters" },
  { value: "agency", label: "Trade agency", hint: "Chamber or promotion body" },
  { value: "other", label: "Other", hint: "Just exploring" },
];

function Choice({
  selected,
  onClick,
  title,
  hint,
}: {
  selected: boolean;
  onClick: () => void;
  title: string;
  hint?: string;
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onClick}
      className={`rounded-xl border p-3 text-left transition-all duration-200 ${
        selected
          ? "border-ember bg-ember/10 text-cream"
          : "border-ink-line text-sage hover:border-sage-dim hover:text-cream"
      }`}
    >
      <span className="block text-sm font-medium">{title}</span>
      {hint && <span className="mt-0.5 block text-xs text-sage-dim">{hint}</span>}
    </button>
  );
}

function OnboardingForm({
  initial,
  exporters,
  countries,
}: {
  initial: Profile | null;
  exporters: Country[];
  countries: Country[];
}) {
  const router = useRouter();
  const save = useSaveProfile();
  const editing = initial !== null;
  const [step, setStep] = useState<1 | 2>(1);
  const [exporter, setExporter] = useState(initial?.exporter.code);
  const [role, setRole] = useState<Role | undefined>(initial?.role);
  const [goal, setGoal] = useState<Goal>(initial?.goal ?? "sell");
  const buyerOnly = goal === "buy";
  const [products, setProducts] = useState<Product[]>(initial?.products ?? []);
  const [markets, setMarkets] = useState<string[]>(
    initial?.current_markets.map((c) => c.code) ?? [],
  );

  function chooseGoal(next: Goal) {
    if (next === goal) return;
    // Buying checks products against supplier data, selling against ranked markets.
    if ((next === "buy") !== buyerOnly) setProducts([]);
    setGoal(next);
  }

  function chooseExporter(code: string) {
    if (code === exporter) return;
    setExporter(code);
    // Rankings are per exporter country: picked products and markets no longer apply.
    setProducts([]);
    setMarkets([]);
  }

  async function submit() {
    if (!exporter || !role || products.length === 0) return;
    await save.mutateAsync({
      exporter,
      role,
      goal,
      products: products.map((p) => p.hs6),
      current_markets: buyerOnly ? [] : markets,
    });
    router.push(buyerOnly ? "/app/buy" : "/app");
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col px-6 py-14">
      <p className="text-sm text-sage-dim">
        Step {step} of 2 · {editing ? "Edit your preferences" : "Set up your markets"}
      </p>
      <div className="mt-2 h-1 overflow-hidden rounded-full bg-ink-line">
        <div
          className="h-full rounded-full bg-ember transition-[width] duration-500"
          style={{ width: step === 1 ? "50%" : "100%" }}
        />
      </div>

      {step === 1 ? (
        <section key="step-1" className="rise-in mt-10 flex flex-col gap-10">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">What do you want to do?</h1>
            <p className="mt-2 text-sage">You can switch any time; both sections stay open.</p>
            <div role="radiogroup" className="mt-6 grid gap-3 sm:grid-cols-3">
              {GOALS.map((g) => (
                <Choice
                  key={g.value}
                  selected={goal === g.value}
                  onClick={() => chooseGoal(g.value)}
                  title={g.label}
                  hint={g.hint}
                />
              ))}
            </div>
          </div>
          <div>
            <h2 className="text-xl font-semibold tracking-tight">Where is your business based?</h2>
            <p className="mt-2 text-sm text-sage">
              {buyerOnly
                ? "We compare suppliers for buyers in this country."
                : "Every ranking is built for exporters in this country."}
            </p>
            <div role="radiogroup" className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
              {exporters.map((c) => (
                <Choice
                  key={c.code}
                  selected={exporter === c.code}
                  onClick={() => chooseExporter(c.code)}
                  title={c.name}
                />
              ))}
            </div>
          </div>
          <div>
            <h2 className="text-xl font-semibold tracking-tight">What best describes you?</h2>
            <div role="radiogroup" className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {ROLES.map((r) => (
                <Choice
                  key={r.value}
                  selected={role === r.value}
                  onClick={() => setRole(r.value)}
                  title={r.label}
                  hint={r.hint}
                />
              ))}
            </div>
          </div>
          <div className="flex justify-end">
            <Button disabled={!exporter || !role} onClick={() => setStep(2)}>
              Continue
            </Button>
          </div>
        </section>
      ) : (
        <section key="step-2" className="rise-in mt-10 flex flex-col gap-10">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">
              {buyerOnly ? "What do you buy?" : "What do you export?"}
            </h1>
            <p className="mt-2 text-sage">
              Pick up to {MAX_PRODUCTS} products.{" "}
              {buyerOnly
                ? "We'll compare the best countries to buy each from."
                : "Your dashboard shows the best new markets for each."}
            </p>
            <div className="mt-6">
              <ProductPicker
                mode={buyerOnly ? "buy" : "sell"}
                exporter={exporter}
                exclude={products.map((p) => p.hs6)}
                disabled={products.length >= MAX_PRODUCTS}
                placeholder={
                  products.length >= MAX_PRODUCTS
                    ? `That's the maximum of ${MAX_PRODUCTS}`
                    : "Describe a product, e.g. cotton towels"
                }
                onSelect={(p) => setProducts((list) => [...list, p])}
              />
            </div>
            {products.length > 0 && (
              <ul className="mt-4 flex flex-col gap-2">
                {products.map((p) => (
                  <li
                    key={p.hs6}
                    className="rise-in flex items-center justify-between gap-3 rounded-xl border border-ink-line bg-ink-raised px-4 py-3"
                  >
                    <span>
                      <span className="block text-sm">{shortProductName(p.description)}</span>
                      <span className="text-xs text-sage-dim">HS {p.hs6}</span>
                    </span>
                    <button
                      type="button"
                      aria-label={`Remove ${shortProductName(p.description)}`}
                      onClick={() => setProducts((list) => list.filter((x) => x.hs6 !== p.hs6))}
                      className="rounded-full px-2 text-sage hover:text-cream"
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {!buyerOnly && (
            <div>
              <h2 className="text-xl font-semibold tracking-tight">
                Where do you already sell? <span className="text-sage-dim">(optional)</span>
              </h2>
              <p className="mt-2 text-sm text-sage">
                We’ll mark these markets and focus your top picks on new ones.
              </p>
              <div className="mt-4">
                <CountryMultiSelect
                  countries={countries}
                  selected={markets}
                  onChange={setMarkets}
                  exclude={exporter}
                />
              </div>
            </div>
          )}

          {save.error && (
            <p role="alert" className="rounded-lg bg-ember/10 px-3 py-2 text-sm text-ember">
              {save.error.message}
            </p>
          )}

          <div className="flex justify-between">
            <Button variant="ghost" onClick={() => setStep(1)}>
              ← Back
            </Button>
            <Button disabled={products.length === 0 || save.isPending} onClick={submit}>
              {save.isPending
                ? "Saving…"
                : editing
                  ? "Save changes"
                  : buyerOnly
                    ? "Show me suppliers"
                    : "Show my markets"}
            </Button>
          </div>
        </section>
      )}
    </div>
  );
}

export function Onboarding() {
  const profile = useProfile();
  const exporters = useExporters();
  const countries = useCountries();

  if (profile.isPending || exporters.isPending || countries.isPending) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-sage">Loading…</div>
    );
  }
  if (profile.isError || exporters.isError || countries.isError) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-sage">
        Couldn’t load your preferences. Please refresh.
      </div>
    );
  }
  return (
    <OnboardingForm initial={profile.data} exporters={exporters.data} countries={countries.data} />
  );
}
