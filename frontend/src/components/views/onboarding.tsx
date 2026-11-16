"use client";

import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Check, LogOut, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, type ReactNode, useEffect, useRef, useState } from "react";

import { Logo } from "@/components/brand/logo";
import {
  CountryField,
  GoalField,
  guessCountry,
  MarketsField,
  MAX_PRODUCTS,
  ProductsField,
  RoleField,
  sellsAbroad,
  usePreferences,
} from "@/components/onboarding/preferences";
import { Callout } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/empty";
import {
  type Country,
  type Profile,
  useCountries,
  useExporters,
  useProfile,
  useSaveProfile,
} from "@/lib/api/queries";
import { signOut } from "@/lib/auth";

type Step = "goal" | "country" | "role" | "products" | "markets";

function Frame({ children, footer }: { children: ReactNode; footer?: ReactNode }) {
  const router = useRouter();
  const client = useQueryClient();
  async function onSignOut() {
    await signOut();
    client.clear();
    router.replace("/");
    router.refresh();
  }
  return (
    <div className="flex min-h-dvh flex-col bg-canvas">
      <header className="flex h-16 items-center justify-between gap-3 px-4 sm:px-6">
        <Logo href="/app" />
        <button
          type="button"
          onClick={onSignOut}
          className="inline-flex h-10 items-center gap-2 rounded-xl px-3 text-sm text-muted transition-colors hover:bg-surface-2 hover:text-fg focus-visible:outline-2 focus-visible:outline-brand"
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </button>
      </header>
      {children}
      {footer}
    </div>
  );
}

function Progress({ index, total }: { index: number; total: number }) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm text-muted tabular-nums">
        Step {index + 1} of {total}
      </p>
      <div
        role="progressbar"
        aria-label="Setup progress"
        aria-valuemin={1}
        aria-valuemax={total}
        aria-valuenow={index + 1}
        className="grid gap-1.5"
        style={{ gridTemplateColumns: `repeat(${total}, minmax(0, 1fr))` }}
      >
        {Array.from({ length: total }, (_, i) => (
          <span key={i} className="h-1.5 overflow-hidden rounded-full bg-line">
            <span
              className={`block h-full rounded-full bg-brand transition-[width] duration-300 ease-out ${
                i <= index ? "w-full" : "w-0"
              }`}
            />
          </span>
        ))}
      </div>
    </div>
  );
}

function Wizard({
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
  const prefs = usePreferences(initial);
  const { draft } = prefs;
  const [suggested] = useState(() => {
    const code = guessCountry();
    return exporters.some((c) => c.code === code) ? code : undefined;
  });
  const [step, setStep] = useState<Step>("goal");
  const heading = useRef<HTMLHeadingElement>(null);
  const first = useRef(true);

  const steps: Step[] = [
    "goal",
    "country",
    "role",
    "products",
    ...(sellsAbroad(draft.goal) ? (["markets"] as const) : []),
  ];
  const index = Math.max(0, steps.indexOf(step));
  const last = index === steps.length - 1;
  const buyer = draft.goal === "buy";
  const countryName = exporters.find((c) => c.code === draft.exporter)?.name;

  // Each new question takes focus, so screen readers announce it.
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    heading.current?.focus();
  }, [step]);

  const ready =
    step === "goal" ||
    (step === "country" && Boolean(draft.exporter ?? suggested)) ||
    (step === "role" && !prefs.missing.role) ||
    (step === "products" && !prefs.missing.products) ||
    step === "markets";

  async function next(e: FormEvent) {
    e.preventDefault();
    if (!ready) return;
    if (step === "country" && !draft.exporter && suggested) prefs.chooseExporter(suggested);
    if (!last) {
      setStep(steps[index + 1]);
      return;
    }
    const body = prefs.input();
    if (!body) return;
    await save.mutateAsync(body);
    router.push("/app");
  }

  function back() {
    if (index > 0) setStep(steps[index - 1]);
  }

  const copy: Record<Step, { title: string; text: string }> = {
    goal: {
      title: "What do you want to do?",
      text: "We’ll set up Whitespace around it. You can change this any time in Settings.",
    },
    country: {
      title: "Where is your business based?",
      text: buyer
        ? "We compare suppliers and prices for buyers in this country."
        : "Every market ranking is built for exporters in this country.",
    },
    role: { title: "What best describes you?", text: "So we can explain things the right way." },
    products: {
      title: buyer ? "What do you buy?" : "What do you export?",
      text: `Add up to ${MAX_PRODUCTS} products. ${
        buyer
          ? "We’ll compare the best countries to buy each from."
          : `We’ll rank the best markets for each, for exporters in ${countryName ?? "your country"}.`
      }`,
    },
    markets: {
      title: "Where do you already sell?",
      text: "Optional. We’ll mark these markets and point your top picks at new ones.",
    },
  };

  const finish = save.isPending
    ? "Saving…"
    : initial
      ? "Save changes"
      : buyer
        ? "Show me suppliers"
        : "Show my markets";

  const footer = (
    <div className="sticky bottom-0 border-t border-line bg-canvas/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl">
      <div className="mx-auto flex w-full max-w-2xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
        {index > 0 ? (
          <Button type="button" variant="ghost" size="lg" className="px-4" onClick={back}>
            <ArrowLeft /> Back
          </Button>
        ) : initial ? (
          <Link
            href="/app"
            className="inline-flex h-12 items-center rounded-xl px-4 text-sm text-muted hover:text-fg"
          >
            Cancel
          </Link>
        ) : (
          <span />
        )}
        <Button
          type="submit"
          form="onboarding"
          size="lg"
          disabled={!ready || save.isPending}
          className="min-w-36"
        >
          {last ? (
            <>
              {finish} {!save.isPending && <Check />}
            </>
          ) : (
            <>
              Continue <ArrowRight />
            </>
          )}
        </Button>
      </div>
    </div>
  );

  return (
    <Frame footer={footer}>
      <form
        id="onboarding"
        onSubmit={next}
        className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-8 px-4 pt-4 pb-10 sm:px-6 sm:pt-10"
      >
        <Progress index={index} total={steps.length} />

        <section key={step} className="rise-in flex flex-col gap-6" aria-labelledby="question">
          <div>
            <h1
              id="question"
              ref={heading}
              tabIndex={-1}
              className="text-2xl font-semibold tracking-tight text-balance outline-none sm:text-3xl"
            >
              {copy[step].title}
            </h1>
            <p className="mt-2 text-pretty text-muted">{copy[step].text}</p>
          </div>

          {step === "goal" && (
            <GoalField label={copy.goal.title} value={draft.goal} onChange={prefs.chooseGoal} />
          )}
          {step === "country" && (
            <CountryField
              label={copy.country.title}
              exporters={exporters}
              value={draft.exporter ?? suggested}
              onChange={prefs.chooseExporter}
              suggested={suggested}
            />
          )}
          {step === "role" && (
            <RoleField
              label={copy.role.title}
              goal={draft.goal}
              value={draft.role}
              onChange={prefs.chooseRole}
            />
          )}
          {step === "products" && (
            <ProductsField
              goal={draft.goal}
              exporter={draft.exporter}
              products={draft.products}
              onAdd={prefs.addProduct}
              onRemove={prefs.removeProduct}
              autoFocus
            />
          )}
          {step === "markets" && (
            <MarketsField
              countries={countries}
              exporter={draft.exporter}
              selected={draft.markets}
              onChange={prefs.setMarkets}
            />
          )}

          {prefs.notice && (
            <Callout tone="caution">
              <span className="flex items-start gap-2">
                <RotateCcw aria-hidden className="mt-1 h-4 w-4 shrink-0" />
                {prefs.notice}
              </span>
            </Callout>
          )}
          {save.error && (
            <div role="alert">
              <Callout tone="negative">{save.error.message}</Callout>
            </div>
          )}
        </section>
      </form>
    </Frame>
  );
}

export function Onboarding() {
  const profile = useProfile();
  const exporters = useExporters();
  const countries = useCountries();

  if (profile.isError || exporters.isError || countries.isError) {
    return (
      <Frame>
        <div className="mx-auto flex max-w-md flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
          <h1 className="text-xl font-semibold">Couldn’t load your setup</h1>
          <p className="text-sm text-muted">Check your connection, then try again.</p>
          <Button
            variant="secondary"
            onClick={() => {
              void profile.refetch();
              void exporters.refetch();
              void countries.refetch();
            }}
          >
            <RotateCcw /> Try again
          </Button>
        </div>
      </Frame>
    );
  }
  if (!profile.isSuccess || !exporters.data || !countries.data) {
    return (
      <Frame>
        <div className="mx-auto flex w-full max-w-2xl flex-col gap-8 px-4 pt-4 sm:px-6 sm:pt-10">
          <Skeleton className="h-8 w-full max-w-xs" />
          <Skeleton className="h-10 w-3/4" />
          <div className="grid gap-3">
            <Skeleton className="h-20" />
            <Skeleton className="h-20" />
            <Skeleton className="h-20" />
          </div>
        </div>
      </Frame>
    );
  }
  return <Wizard initial={profile.data} exporters={exporters.data} countries={countries.data} />;
}
