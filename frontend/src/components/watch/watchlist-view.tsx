"use client";

import { BellRing, CalendarClock, FileText, Inbox, Radar, TrendingUp, X } from "lucide-react";
import Link from "next/link";
import type { CSSProperties } from "react";

import { Badge } from "@/components/ui/badge";
import { Button, ButtonLink } from "@/components/ui/button";
import { Card, CardHeader, Page, PageHeader } from "@/components/ui/card";
import { EmptyState, Skeleton } from "@/components/ui/empty";
import { NotificationItem } from "@/components/watch/notification-item";
import {
  type Watch,
  useMarkRead,
  useNotifications,
  useRemoveWatch,
  useWatches,
} from "@/lib/api/watch";
import { capitalize } from "@/lib/format";

const RECENT_ALERTS = 30;

/** Group watches by product, keeping the order they were added. */
function byProduct(watches: Watch[]): [Watch["product"], Watch[]][] {
  const groups = new Map<string, [Watch["product"], Watch[]]>();
  for (const w of watches) {
    const group = groups.get(w.product.hs6) ?? [w.product, []];
    group[1].push(w);
    groups.set(w.product.hs6, group);
  }
  return [...groups.values()];
}

function WatchRow({ watch }: { watch: Watch }) {
  const remove = useRemoveWatch();
  const market = `/app/markets/${watch.product.hs6}/${watch.market.code}`;
  const from = `?exporter=${watch.exporter.code}`;
  return (
    <li className="group flex items-center gap-3 rounded-xl px-3 py-2.5 transition-colors hover:bg-surface-2">
      <Link href={`${market}${from}`} className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium">{watch.market.name}</span>
        <span className="text-xs text-muted">from {watch.exporter.name}</span>
      </Link>
      {watch.alerts_available ? (
        <Badge tone="positive" icon={<BellRing />}>
          Monthly alerts
        </Badge>
      ) : (
        <Badge tone="neutral" icon={<CalendarClock />}>
          Yearly data
        </Badge>
      )}
      <Link
        href={`${market}/deal${from}`}
        aria-label={`Deal sheet for ${watch.market.name}`}
        title="Deal sheet: costs, route and buyers"
        className="inline-flex items-center gap-1.5 rounded-lg p-1.5 text-xs font-medium text-muted transition-colors hover:bg-brand-soft hover:text-brand"
      >
        <FileText className="h-4 w-4" aria-hidden />
        <span className="hidden sm:inline">Deal sheet</span>
      </Link>
      <button
        type="button"
        aria-label={`Stop watching ${watch.market.name}`}
        disabled={remove.isPending}
        onClick={() => remove.mutate(watch.id)}
        className="rounded-lg p-1.5 text-subtle transition-colors hover:bg-negative-soft hover:text-negative"
      >
        <X className="h-4 w-4" />
      </button>
    </li>
  );
}

export function WatchlistView() {
  const watches = useWatches();
  const alerts = useNotifications(RECENT_ALERTS);
  const markRead = useMarkRead();
  const unread = alerts.data?.unread ?? 0;

  return (
    <Page>
      <PageHeader
        title="Watchlist"
        description="Markets you follow. When fresh monthly customs data shows a real move, we tell you here and on the bell."
        actions={
          <ButtonLink href="/app/markets" variant="secondary">
            <TrendingUp /> Find markets
          </ButtonLink>
        }
      />

      <div className="grid gap-4 lg:grid-cols-5">
        <Card className="rise-in flex flex-col gap-4 p-5 lg:col-span-3">
          <CardHeader
            icon={<Radar />}
            title="Following"
            description="Monthly alerts cover EU countries and the United States; other markets update yearly."
          />
          {watches.isPending ? (
            <Skeleton className="h-40" />
          ) : !watches.data?.length ? (
            <EmptyState
              icon={<BellRing />}
              title="Nothing watched yet"
              action={
                <ButtonLink href="/app/markets" variant="primary">
                  Find a market to watch
                </ButtonLink>
              }
            >
              Open any market and press Watch. We’ll alert you when its imports jump or fall, or
              when rivals lose ground.
            </EmptyState>
          ) : (
            <div className="flex flex-col gap-5">
              {byProduct(watches.data).map(([product, items]) => (
                <section key={product.hs6}>
                  <h3 className="px-3 text-xs font-semibold tracking-wide text-subtle uppercase">
                    {capitalize(product.name)}
                  </h3>
                  <ul className="mt-1 flex flex-col">
                    {items.map((w) => (
                      <WatchRow key={w.id} watch={w} />
                    ))}
                  </ul>
                </section>
              ))}
            </div>
          )}
        </Card>

        <Card
          className="rise-in flex flex-col gap-3 p-5 lg:col-span-2"
          style={{ "--delay": "80ms" } as CSSProperties}
        >
          <CardHeader
            icon={<Inbox />}
            title="Recent alerts"
            description={unread ? `${unread} unread` : "All caught up"}
            action={
              unread > 0 ? (
                <Button variant="ghost" size="sm" onClick={() => markRead.mutate({ all: true })}>
                  Mark all read
                </Button>
              ) : undefined
            }
          />
          {alerts.isPending ? (
            <Skeleton className="h-32" />
          ) : alerts.data?.items.length ? (
            <ul className="-mx-2 flex flex-col">
              {alerts.data.items.map((n) => (
                <li key={n.id}>
                  <NotificationItem
                    notification={n}
                    onOpen={() => !n.read_at && markRead.mutate({ ids: [n.id] })}
                  />
                </li>
              ))}
            </ul>
          ) : (
            <p className="rounded-xl bg-surface-2 p-4 text-sm text-muted">
              No alerts yet. They arrive when new monthly data shows a move of 20% or more in
              imports, or 2+ points in shares.
            </p>
          )}
        </Card>
      </div>
    </Page>
  );
}
