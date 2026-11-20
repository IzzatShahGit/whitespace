"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Plus, Sprout } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { VerdictBadge } from "@/components/markets/verdict";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { useGrowRange } from "@/lib/api/grow";
import { type Profile, useSaveProfile } from "@/lib/api/queries";
import { capitalize, money, shortProductName } from "@/lib/format";

const MAX_PRODUCTS = 5;

/** "Grow your range": close relatives of what the user sells, one click to add. */
export function GrowRange({ profile }: { profile: Profile }) {
  const ideas = useGrowRange(true);
  const save = useSaveProfile();
  const client = useQueryClient();
  const [all, setAll] = useState(false);
  const full = profile.products.length >= MAX_PRODUCTS;
  if (!ideas.data?.ideas.length) return null;

  function add(hs6: string) {
    save.mutate(
      {
        exporter: profile.exporter.code,
        role: profile.role,
        goal: profile.goal,
        products: [...profile.products.map((p) => p.hs6), hs6],
        current_markets: profile.current_markets.map((c) => c.code),
      },
      { onSuccess: () => void client.invalidateQueries({ queryKey: ["grow"] }) },
    );
  }

  const more = ideas.data.ideas.length - 3;
  return (
    <Card className="rise-in flex flex-col gap-4 p-5 sm:p-6">
      <CardHeader
        icon={<Sprout />}
        action={
          more > 0 ? (
            <Button variant="ghost" size="sm" onClick={() => setAll((a) => !a)}>
              {all ? "Show fewer" : `${more} more`}
            </Button>
          ) : undefined
        }
        title="Grow your range"
        description={`Products close to yours that ${profile.exporter.name} already exports competitively, and where they sell best.`}
      />
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {ideas.data.ideas.slice(0, all ? undefined : 3).map((idea) => (
          <li
            key={idea.product.hs6}
            className="flex flex-col gap-2 rounded-xl border border-line p-4 transition-colors hover:border-line-strong"
          >
            <Link href={`/app/markets/${idea.product.hs6}`} className="group flex flex-col gap-1">
              <span className="font-medium group-hover:text-brand">
                {capitalize(idea.product.name)}
              </span>
              <span className="line-clamp-2 text-xs text-subtle" title={idea.product.description}>
                {shortProductName(idea.product.description)} · HS {idea.product.hs6}
              </span>
              <span className="text-xs text-muted">
                {idea.strong_markets} strong of {idea.markets} markets
                {idea.same_family ? " · same family as yours" : ""}
              </span>
            </Link>
            <div className="flex items-center justify-between gap-2 text-sm">
              <span className="truncate">
                Best: {idea.top.market.name}{" "}
                <span className="text-xs text-muted">{money(idea.top.market_imports_usd)}</span>
              </span>
              <VerdictBadge verdict={idea.top.verdict} />
            </div>
            <button
              type="button"
              disabled={full || save.isPending}
              title={full ? `You can track up to ${MAX_PRODUCTS} products` : undefined}
              onClick={() => add(idea.product.hs6)}
              className="mt-1 inline-flex items-center gap-1 self-start text-xs font-medium text-brand hover:underline disabled:text-subtle disabled:no-underline"
            >
              <Plus className="h-3.5 w-3.5" /> Add to my products
            </button>
          </li>
        ))}
      </ul>
      {save.error && <p className="text-sm text-negative">{save.error.message}</p>}
    </Card>
  );
}
