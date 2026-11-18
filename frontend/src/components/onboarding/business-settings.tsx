"use client";

import { Building2, Globe2, Package, RotateCcw, Target, UserRound } from "lucide-react";
import { type CSSProperties, type FormEvent } from "react";

import {
  changed,
  CountryField,
  GoalField,
  MarketsField,
  ProductsField,
  RoleField,
  sellsAbroad,
  usePreferences,
} from "@/components/onboarding/preferences";
import { Callout } from "@/components/ui/badge";
import { Button, ButtonLink } from "@/components/ui/button";
import { LetterheadCard } from "@/components/quotes/letterhead-card";
import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState, Skeleton } from "@/components/ui/empty";
import {
  type Country,
  type Profile,
  useCountries,
  useExporters,
  useProfile,
  useSaveProfile,
} from "@/lib/api/queries";

function Form({
  profile,
  exporters,
  countries,
}: {
  profile: Profile;
  exporters: Country[];
  countries: Country[];
}) {
  const save = useSaveProfile();
  const prefs = usePreferences(profile);
  const { draft } = prefs;
  const dirty = changed(draft, profile);
  const saved = save.isSuccess && !dirty;

  function submit(e: FormEvent) {
    e.preventDefault();
    const body = prefs.input();
    if (!body || !dirty) return;
    save.mutate(body, {
      onSuccess: () => prefs.dismissNotice(),
    });
  }

  const problem = prefs.missing.products
    ? "Add at least one product to save."
    : prefs.missing.role
      ? "Choose what best describes you."
      : undefined;

  return (
    <form onSubmit={submit} className="flex flex-col gap-6" aria-label="Business preferences">
      <Card className="rise-in p-5 sm:p-6">
        <CardHeader
          icon={<Target />}
          title="What you do"
          description="We set up Home around selling, buying, or both."
        />
        <div className="mt-5">
          <GoalField label="What you do" value={draft.goal} onChange={prefs.chooseGoal} compact />
        </div>
      </Card>

      <Card className="rise-in p-5 sm:p-6" style={{ "--delay": "40ms" } as CSSProperties}>
        <CardHeader
          icon={<Building2 />}
          title="Where your business is based"
          description="Rankings and supplier prices are built for this country. Changing it clears your products and markets."
        />
        <div className="mt-5">
          <CountryField
            label="Where your business is based"
            exporters={exporters}
            value={draft.exporter}
            onChange={prefs.chooseExporter}
          />
        </div>
      </Card>

      <Card className="rise-in p-5 sm:p-6" style={{ "--delay": "80ms" } as CSSProperties}>
        <CardHeader icon={<UserRound />} title="Your role" />
        <div className="mt-5">
          <RoleField
            label="Your role"
            goal={draft.goal}
            value={draft.role}
            onChange={prefs.chooseRole}
          />
        </div>
      </Card>

      <Card
        className="rise-in relative z-20 p-5 sm:p-6"
        style={{ "--delay": "120ms" } as CSSProperties}
      >
        <CardHeader
          icon={<Package />}
          title={draft.goal === "buy" ? "Products you buy" : "Products you sell"}
          description={
            draft.goal === "buy"
              ? "We compare the best countries to buy each from."
              : "Home shows the best new markets for each."
          }
        />
        <div className="mt-5">
          <ProductsField
            goal={draft.goal}
            exporter={draft.exporter}
            products={draft.products}
            onAdd={prefs.addProduct}
            onRemove={prefs.removeProduct}
          />
        </div>
      </Card>

      {sellsAbroad(draft.goal) && (
        <Card
          className="rise-in relative z-10 p-5 sm:p-6"
          style={{ "--delay": "160ms" } as CSSProperties}
        >
          <CardHeader
            icon={<Globe2 />}
            title="Markets you already sell to"
            description="Optional. We mark them and point your top picks at new ones."
          />
          <div className="mt-5">
            <MarketsField
              countries={countries}
              exporter={draft.exporter}
              selected={draft.markets}
              onChange={prefs.setMarkets}
            />
          </div>
        </Card>
      )}

      {prefs.notice && (
        <Callout tone="caution">
          <span className="flex items-start gap-2">
            <RotateCcw aria-hidden className="mt-1 h-4 w-4 shrink-0" />
            {prefs.notice}
          </span>
        </Callout>
      )}

      <div className="sticky bottom-20 z-30 lg:bottom-4">
        <div
          className={`flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line bg-surface/95 px-4 py-3 backdrop-blur-xl transition-shadow ${
            dirty ? "shadow-pop" : "shadow-card"
          }`}
        >
          <p className="text-sm text-muted" aria-live="polite">
            {save.error ? (
              <span className="text-negative">{save.error.message}</span>
            ) : dirty ? (
              (problem ?? "You have unsaved changes.")
            ) : saved ? (
              <span className="text-positive">Saved. Home is updated.</span>
            ) : (
              "Everything is saved."
            )}
          </p>
          <div className="flex gap-2">
            {dirty && (
              <Button type="button" variant="ghost" onClick={() => prefs.reset(profile)}>
                Discard
              </Button>
            )}
            <Button type="submit" disabled={!dirty || Boolean(problem) || save.isPending}>
              {save.isPending ? "Saving…" : "Save changes"}
            </Button>
          </div>
        </div>
      </div>
    </form>
  );
}

/** Settings → Business: the onboarding answers, all on one page, one Save. */
export function BusinessSettings() {
  const profile = useProfile();
  const exporters = useExporters();
  const countries = useCountries();

  if (profile.isError || exporters.isError || countries.isError) {
    return (
      <EmptyState
        icon={<RotateCcw />}
        title="Couldn’t load your business details"
        action={
          <Button
            variant="secondary"
            onClick={() => {
              void profile.refetch();
              void exporters.refetch();
              void countries.refetch();
            }}
          >
            Try again
          </Button>
        }
      >
        Check your connection, then try again.
      </EmptyState>
    );
  }
  if (!profile.isSuccess || !exporters.data || !countries.data) {
    return (
      <>
        <Skeleton className="h-44" />
        <Skeleton className="h-64" />
        <Skeleton className="h-48" />
      </>
    );
  }
  if (!profile.data) {
    return (
      <EmptyState
        icon={<Building2 />}
        title="Set up your business first"
        action={<ButtonLink href="/onboarding">Start setup</ButtonLink>}
      >
        Five quick questions: what you do, where you’re based, and your products.
      </EmptyState>
    );
  }
  return (
    <>
      <Form profile={profile.data} exporters={exporters.data} countries={countries.data} />
      <LetterheadCard />
    </>
  );
}
