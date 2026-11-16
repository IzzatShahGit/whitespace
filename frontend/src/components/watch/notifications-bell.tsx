"use client";

import { Bell, CheckCheck } from "lucide-react";
import Link from "next/link";

import { Popover } from "@/components/ui/menu";
import { NotificationItem } from "@/components/watch/notification-item";
import { useMarkRead, useNotifications } from "@/lib/api/watch";

const SHOWN = 6;

/** The bell in the top bar: unread count, the latest alerts, and a way to clear them. */
export function NotificationsBell() {
  const notifications = useNotifications(SHOWN);
  const markRead = useMarkRead();
  const unread = notifications.data?.unread ?? 0;

  return (
    <Popover
      label={unread ? `Alerts, ${unread} unread` : "Alerts"}
      width="w-[min(24rem,calc(100vw-2rem))]"
      button={(open) => (
        <span
          className={`relative flex h-10 w-10 items-center justify-center rounded-full border border-line bg-surface shadow-card transition-colors hover:border-line-strong ${
            open ? "text-fg" : "text-muted"
          }`}
        >
          <Bell className="h-[18px] w-[18px]" />
          {unread > 0 && (
            <span className="absolute -top-0.5 -right-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-accent px-1 text-xs font-semibold text-white">
              {unread > 9 ? "9+" : unread}
            </span>
          )}
        </span>
      )}
    >
      {(close) => (
        <div className="flex flex-col">
          <div className="flex items-center justify-between px-3 py-2">
            <p className="text-sm font-semibold">Alerts</p>
            {unread > 0 && (
              <button
                type="button"
                onClick={() => markRead.mutate({ all: true })}
                className="flex items-center gap-1 text-xs text-brand hover:underline"
              >
                <CheckCheck className="h-3.5 w-3.5" /> Mark all read
              </button>
            )}
          </div>
          {notifications.data?.items.length ? (
            <ul className="flex max-h-[60vh] flex-col overflow-auto">
              {notifications.data.items.map((n) => (
                <li key={n.id}>
                  <NotificationItem
                    notification={n}
                    onOpen={() => {
                      if (!n.read_at) markRead.mutate({ ids: [n.id] });
                      close();
                    }}
                  />
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-3 py-6 text-center text-sm text-muted">
              No alerts yet. Watch a market and we’ll tell you when its imports or shares move.
            </p>
          )}
          <Link
            href="/app/watchlist"
            onClick={close}
            className="mt-1 rounded-xl px-3 py-2 text-center text-sm text-brand hover:bg-surface-2"
          >
            Open watchlist
          </Link>
        </div>
      )}
    </Popover>
  );
}
